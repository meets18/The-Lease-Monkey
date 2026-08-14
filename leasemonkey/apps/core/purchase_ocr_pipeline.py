"""
purchase_ocr_pipeline.py
------------------------
Asynchronous OCR-based identity document validation for PurchaseRequest.

Runs in a background thread (fire-and-forget) triggered from the purchase
request submit view. Never blocks the HTTP response and never raises
exceptions to the caller — all failures are stored as error_message on the
PurchaseRequestOCRValidation record.

Requires the same dependencies as the landowner application pipeline:
  pip install pytesseract rapidfuzz pdf2image Pillow
  Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki
  Set TESSERACT_CMD in .env  e.g.  C:\\Program Files\\Tesseract-OCR\\tesseract.exe
"""

import os
import re
import logging

import django
from django.utils import timezone

from apps.accounts.ocr_pipeline import (
    AADHAAR_KEYWORDS,
    PAN_KEYWORDS,
    RISK_WEIGHTS,
    CONFIDENCE_THRESHOLD,
    _process_document,
    _fuzzy_name_match,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def run_purchase_ocr_validation(request_id: int) -> None:
    """
    Main entry point called from a background thread.
    Loads the PurchaseRequest, runs OCR on Aadhaar + PAN documents,
    computes risk score, and saves the PurchaseRequestOCRValidation record.
    """
    try:
        django.setup()
    except RuntimeError:
        pass

    from apps.core.models import PurchaseRequest, PurchaseRequestOCRValidation

    try:
        pr = PurchaseRequest.objects.get(pk=request_id)
        ocr_rec = PurchaseRequestOCRValidation.objects.get(request=pr)
    except Exception as exc:
        logger.error(f"[PurchaseOCR] Could not load request #{request_id}: {exc}")
        return

    # Mark as processing
    ocr_rec.validation_status = 'processing'
    ocr_rec.save(update_fields=['validation_status'])

    try:
        _run(pr, ocr_rec)
    except Exception as exc:
        logger.exception(f"[PurchaseOCR] Unexpected failure for request #{request_id}")
        ocr_rec.validation_status = 'failed'
        ocr_rec.error_message = str(exc)
        ocr_rec.risk_level = 'failed'
        ocr_rec.processed_at = timezone.now()
        ocr_rec.save()


def _run(pr, ocr_rec) -> None:
    """Core OCR pipeline — separated so exceptions bubble up to the wrapper."""
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = os.environ.get(
            'TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        )
    except ImportError:
        raise RuntimeError("pytesseract is not installed. Run: pip install pytesseract")

    flags = []
    risk_score = 0

    # ----------------------------------------------------------------
    # Process Aadhaar document
    # ----------------------------------------------------------------
    if pr.aadhaar_document:
        aadhaar_result = _process_document(
            file_field=pr.aadhaar_document,
            doc_label='Aadhaar',
            keywords=AADHAAR_KEYWORDS,
            number_pattern=r'\d{4}[ \t]?\d{4}[ \t]?\d{4}',
            entered_value=pr.aadhaar_number,
            normalize_fn=lambda s: re.sub(r'\s', '', s),
        )

        ocr_rec.aadhaar_raw_text          = aadhaar_result['raw_text']
        ocr_rec.aadhaar_doc_type_detected = aadhaar_result['doc_type_detected']
        ocr_rec.aadhaar_number_found      = aadhaar_result['number_found']
        ocr_rec.aadhaar_number_match      = aadhaar_result['number_match']
        ocr_rec.aadhaar_ocr_number        = aadhaar_result['ocr_number']
        ocr_rec.aadhaar_confidence        = aadhaar_result['confidence']

        if not aadhaar_result['doc_type_detected']:
            risk_score += RISK_WEIGHTS['aadhaar_doc_type_mismatch']
            flags.append('Document Type Mismatch — Aadhaar keywords not found')
        if not aadhaar_result['number_found']:
            risk_score += RISK_WEIGHTS['aadhaar_number_not_found']
            flags.append('Aadhaar Number Not Found in Document')
        elif not aadhaar_result['number_match']:
            risk_score += RISK_WEIGHTS['aadhaar_number_mismatch']
            flags.append(
                f"Aadhaar Number Mismatch — Entered: {pr.aadhaar_number}, "
                f"OCR Read: {aadhaar_result['ocr_number']}"
            )
        if aadhaar_result['confidence'] is not None and aadhaar_result['confidence'] < CONFIDENCE_THRESHOLD:
            risk_score += RISK_WEIGHTS['aadhaar_low_confidence']
            flags.append(f"Low OCR Confidence (Aadhaar) — {aadhaar_result['confidence']:.0f}%")
    else:
        ocr_rec.aadhaar_raw_text = ''
        ocr_rec.aadhaar_doc_type_detected = None
        ocr_rec.aadhaar_number_found = None
        ocr_rec.aadhaar_number_match = None
        ocr_rec.aadhaar_ocr_number = ''
        ocr_rec.aadhaar_confidence = None
        flags.append('Aadhaar Document Not Uploaded')

    # ----------------------------------------------------------------
    # Process PAN document
    # ----------------------------------------------------------------
    if pr.pan_document:
        pan_result = _process_document(
            file_field=pr.pan_document,
            doc_label='PAN',
            keywords=PAN_KEYWORDS,
            number_pattern=r'[A-Z]{5}[0-9]{4}[A-Z]',
            entered_value=pr.pan_number,
            normalize_fn=lambda s: s.strip().upper(),
        )

        ocr_rec.pan_raw_text          = pan_result['raw_text']
        ocr_rec.pan_doc_type_detected = pan_result['doc_type_detected']
        ocr_rec.pan_number_found      = pan_result['number_found']
        ocr_rec.pan_number_match      = pan_result['number_match']
        ocr_rec.pan_ocr_number        = pan_result['ocr_number']
        ocr_rec.pan_confidence        = pan_result['confidence']

        if not pan_result['doc_type_detected']:
            risk_score += RISK_WEIGHTS['pan_doc_type_mismatch']
            flags.append('Document Type Mismatch — PAN keywords not found')
        if not pan_result['number_found']:
            risk_score += RISK_WEIGHTS['pan_number_not_found']
            flags.append('PAN Number Not Found in Document')
        elif not pan_result['number_match']:
            risk_score += RISK_WEIGHTS['pan_number_mismatch']
            flags.append(f"PAN Number Mismatch — Entered: {pr.pan_number}, OCR Read: {pan_result['ocr_number']}")
        if pan_result['confidence'] is not None and pan_result['confidence'] < CONFIDENCE_THRESHOLD:
            risk_score += RISK_WEIGHTS['pan_low_confidence']
            flags.append(f"Low OCR Confidence (PAN) — {pan_result['confidence']:.0f}%")
    else:
        ocr_rec.pan_raw_text = ''
        ocr_rec.pan_doc_type_detected = None
        ocr_rec.pan_number_found = None
        ocr_rec.pan_number_match = None
        ocr_rec.pan_ocr_number = ''
        ocr_rec.pan_confidence = None
        flags.append('PAN Document Not Uploaded')

    # ----------------------------------------------------------------
    # Optional cross-check: Name matching
    # ----------------------------------------------------------------
    name_score = _fuzzy_name_match(
        form_name=pr.full_name,
        ocr_texts=[ocr_rec.aadhaar_raw_text, ocr_rec.pan_raw_text],
    )
    ocr_rec.name_match_score = name_score
    if name_score is not None and name_score < 80:
        risk_score += RISK_WEIGHTS['name_match_low']
        flags.append(f'Name Match Low — {name_score:.0f}% similarity')

    # ----------------------------------------------------------------
    # Compute final risk level
    # ----------------------------------------------------------------
    risk_score = min(risk_score, 100)
    if risk_score <= 20:
        risk_level = 'low'
    elif risk_score <= 50:
        risk_level = 'medium'
    else:
        risk_level = 'high'

    # ----------------------------------------------------------------
    # Save results
    # ----------------------------------------------------------------
    ocr_rec.risk_score        = risk_score
    ocr_rec.risk_level        = risk_level
    ocr_rec.validation_flags  = flags
    ocr_rec.validation_status = 'completed'
    ocr_rec.processed_at      = timezone.now()
    ocr_rec.save()

    logger.info(
        f"[PurchaseOCR] Request #{ocr_rec.request_id} — "
        f"Risk: {risk_level.upper()} ({risk_score}/100), Flags: {len(flags)}"
    )
