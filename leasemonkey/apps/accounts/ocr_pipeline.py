"""
ocr_pipeline.py
---------------
Asynchronous OCR-based identity document validation for LandownerApplication.

Runs in a background thread (fire-and-forget) triggered from the registration
submit view. Never blocks the HTTP response and never raises exceptions to the
caller — all failures are stored as error_message on the OCRValidation record.

Requires:
  pip install pytesseract rapidfuzz pdf2image Pillow
  Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki
  Set TESSERACT_CMD in .env  e.g.  C:\\Program Files\\Tesseract-OCR\\tesseract.exe
"""

import os
import re
import logging
from datetime import date

import django
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tesseract path configuration
# ---------------------------------------------------------------------------
_TESSERACT_CMD = os.environ.get('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe')

# ---------------------------------------------------------------------------
# Risk scoring weights
# ---------------------------------------------------------------------------
RISK_WEIGHTS = {
    'aadhaar_doc_type_mismatch': 50,
    'aadhaar_number_not_found':  20,
    'aadhaar_number_mismatch':   40,
    'aadhaar_low_confidence':    10,
    'pan_doc_type_mismatch':     50,
    'pan_number_not_found':      20,
    'pan_number_mismatch':       40,
    'pan_low_confidence':        10,
    'name_match_low':            10,
    'dob_not_found':             10,
}

CONFIDENCE_THRESHOLD = 70.0  # %

# Aadhaar keyword markers
AADHAAR_KEYWORDS = [
    'government of india', 'unique identification', 'uidai', 'aadhaar', 'आधार',
    'enrolment', 'enrollment', 'dob', 'male', 'female', 'yob', 'father', 'husband',
]

# PAN keyword markers
PAN_KEYWORDS = [
    'income tax', 'permanent account', 'income tax department',
    'pan', 'govt. of india', 'govt of india', 'permanent', 'account', 'department',
]


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def run_ocr_validation(application_id: int) -> None:
    """
    Main entry point called from a background thread.
    Loads the LandownerApplication, runs OCR on Aadhaar + PAN documents,
    computes risk score, and saves the OCRValidation record.
    """
    # Ensure Django is set up (safe when already set up)
    try:
        django.setup()
    except RuntimeError:
        pass

    from apps.accounts.models import LandownerApplication, OCRValidation

    try:
        app = LandownerApplication.objects.get(pk=application_id)
        ocr_rec = OCRValidation.objects.get(application=app)
    except Exception as exc:
        logger.error(f"[OCR] Could not load application #{application_id}: {exc}")
        return

    # Mark as processing
    ocr_rec.validation_status = 'processing'
    ocr_rec.save(update_fields=['validation_status'])

    try:
        _run(app, ocr_rec)
    except Exception as exc:
        logger.exception(f"[OCR] Unexpected failure for application #{application_id}")
        ocr_rec.validation_status = 'failed'
        ocr_rec.error_message = str(exc)
        ocr_rec.risk_level = 'failed'
        ocr_rec.processed_at = timezone.now()
        ocr_rec.save()


def _run(app, ocr_rec) -> None:
    """Core OCR pipeline — separated so exceptions bubble up to the wrapper."""
    # Configure Tesseract path
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
    except ImportError:
        raise RuntimeError("pytesseract is not installed. Run: pip install pytesseract")

    flags = []
    risk_score = 0

    # ----------------------------------------------------------------
    # Process Aadhaar document
    # ----------------------------------------------------------------
    aadhaar_result = _process_document(
        file_field=app.aadhaar_document,
        doc_label='Aadhaar',
        keywords=AADHAAR_KEYWORDS,
        number_pattern=r'\d{4}[ \t]?\d{4}[ \t]?\d{4}',
        entered_value=app.aadhaar_number,
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
        entered = app.aadhaar_number
        found   = aadhaar_result['ocr_number']
        flags.append(f'Aadhaar Number Mismatch — Entered: {entered}, OCR Read: {found}')
    if aadhaar_result['confidence'] is not None and aadhaar_result['confidence'] < CONFIDENCE_THRESHOLD:
        risk_score += RISK_WEIGHTS['aadhaar_low_confidence']
        flags.append(f"Low OCR Confidence (Aadhaar) — {aadhaar_result['confidence']:.0f}%")

    # ----------------------------------------------------------------
    # Process PAN document
    # ----------------------------------------------------------------
    pan_result = _process_document(
        file_field=app.pan_document,
        doc_label='PAN',
        keywords=PAN_KEYWORDS,
        number_pattern=r'[A-Z]{5}[0-9]{4}[A-Z]',
        entered_value=app.pan_number,
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
        flags.append(f"PAN Number Mismatch — Entered: {app.pan_number}, OCR Read: {pan_result['ocr_number']}")
    if pan_result['confidence'] is not None and pan_result['confidence'] < CONFIDENCE_THRESHOLD:
        risk_score += RISK_WEIGHTS['pan_low_confidence']
        flags.append(f"Low OCR Confidence (PAN) — {pan_result['confidence']:.0f}%")

    # ----------------------------------------------------------------
    # Optional cross-checks: Name matching
    # ----------------------------------------------------------------
    name_score = _fuzzy_name_match(
        form_name=f"{app.first_name} {app.last_name}",
        ocr_texts=[aadhaar_result['raw_text'], pan_result['raw_text']],
    )
    ocr_rec.name_match_score = name_score
    if name_score is not None and name_score < 80:
        risk_score += RISK_WEIGHTS['name_match_low']
        flags.append(f'Name Match Low — {name_score:.0f}% similarity')

    # ----------------------------------------------------------------
    # Optional cross-checks: DOB
    # ----------------------------------------------------------------
    dob_found = _check_dob(
        dob=app.date_of_birth,
        ocr_texts=[aadhaar_result['raw_text'], pan_result['raw_text']],
    )
    ocr_rec.dob_match = dob_found
    if not dob_found:
        risk_score += RISK_WEIGHTS['dob_not_found']
        flags.append('Date of Birth Not Found in Documents')

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
        f"[OCR] Application #{ocr_rec.application_id} — "
        f"Risk: {risk_level.upper()} ({risk_score}/100), Flags: {len(flags)}"
    )


# ===========================================================================
# HELPERS
# ===========================================================================

def _process_document(file_field, doc_label, keywords, number_pattern, entered_value, normalize_fn):
    """
    Opens a document (image or PDF), preprocesses it, runs OCR,
    and returns a structured result dict.
    """
    result = {
        'raw_text': '',
        'confidence': None,
        'doc_type_detected': False,
        'number_found': False,
        'number_match': False,
        'ocr_number': '',
    }

    try:
        from PIL import Image
        import pytesseract

        # Get the absolute file path from Django FileField
        file_path = file_field.path
        ext = os.path.splitext(file_path)[1].lower()

        # Load image (convert PDF first if needed)
        if ext == '.pdf':
            img = _pdf_to_image(file_path)
        else:
            img = Image.open(file_path)

        if img is None:
            raise RuntimeError(f"Could not load {doc_label} document.")

        # --- Strategy: Try Raw Image OCR first ---
        raw_text, confidence = _extract_text(img)
        lower_text = raw_text.lower()

        doc_type_detected = any(kw in lower_text for kw in keywords)
        matches = re.findall(number_pattern, raw_text)
        number_found = len(matches) > 0

        # If we successfully found both the doc keywords and the number on the raw image, use it!
        if doc_type_detected and number_found:
            result['raw_text'] = raw_text
            result['confidence'] = confidence
            result['doc_type_detected'] = True
            result['number_found'] = True
            ocr_number = normalize_fn(matches[0])
            result['ocr_number'] = ocr_number
            result['number_match'] = (ocr_number == normalize_fn(entered_value or ''))
        else:
            # --- Fallback: Preprocess and try again ---
            img_pre = _preprocess_image(img)
            raw_text_pre, confidence_pre = _extract_text(img_pre)
            lower_text_pre = raw_text_pre.lower()

            doc_type_detected_pre = any(kw in lower_text_pre for kw in keywords)
            matches_pre = re.findall(number_pattern, raw_text_pre)
            number_found_pre = len(matches_pre) > 0

            # Use whichever run yielded the target number, preferring preprocessed on success
            if number_found_pre or (not number_found and not doc_type_detected_pre):
                result['raw_text'] = raw_text_pre
                result['confidence'] = confidence_pre
                result['doc_type_detected'] = doc_type_detected_pre
                result['number_found'] = number_found_pre
                if number_found_pre:
                    ocr_number = normalize_fn(matches_pre[0])
                    result['ocr_number'] = ocr_number
                    result['number_match'] = (ocr_number == normalize_fn(entered_value or ''))
            else:
                # Default to raw OCR if preprocessing did worse
                result['raw_text'] = raw_text
                result['confidence'] = confidence
                result['doc_type_detected'] = doc_type_detected
                result['number_found'] = number_found
                if number_found:
                    ocr_number = normalize_fn(matches[0])
                    result['ocr_number'] = ocr_number
                    result['number_match'] = (ocr_number == normalize_fn(entered_value or ''))

    except Exception as exc:
        logger.warning(f"[OCR] Failed to process {doc_label}: {exc}")

    return result


def _pdf_to_image(pdf_path: str):
    """Converts the first page of a PDF to a PIL Image using pdf2image."""
    try:
        from pdf2image import convert_from_path
        pages = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=1)
        if pages:
            return pages[0]
    except Exception as exc:
        logger.warning(f"[OCR] PDF conversion failed for {pdf_path}: {exc}")
    return None


def _preprocess_image(img):
    """
    Applies a series of preprocessing steps to improve OCR accuracy:
    - Convert to grayscale
    - Denoise with median filter
    - Boost contrast
    - Upscale if image is too small (< 1000px wide)
    """
    from PIL import ImageFilter, ImageEnhance, Image

    img = img.convert('L')                           # Grayscale
    img = img.filter(ImageFilter.MedianFilter(3))    # Denoise
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)                      # Boost contrast

    # Upscale small images for better OCR
    if img.width < 1000:
        scale = 1000 / img.width
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    return img


def _extract_text(img) -> tuple:
    """
    Runs pytesseract on a preprocessed PIL Image.
    Returns (raw_text: str, avg_confidence: float | None).
    """
    import pytesseract

    # Extract raw text
    raw_text = pytesseract.image_to_string(img, lang='eng')

    # Extract word-level confidence scores
    try:
        data = pytesseract.image_to_data(img, lang='eng', output_type=pytesseract.Output.DICT)
        confs = [c for c in data['conf'] if isinstance(c, (int, float)) and c >= 0]
        avg_confidence = (sum(confs) / len(confs)) if confs else None
    except Exception:
        avg_confidence = None

    return raw_text, avg_confidence


def _fuzzy_name_match(form_name: str, ocr_texts: list) -> float | None:
    """
    Uses rapidfuzz to compute a fuzzy match score between the applicant's
    full name from the registration form and the best match found in any OCR text.
    Returns a score 0–100 or None if rapidfuzz is unavailable.
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return None

    if not form_name.strip():
        return None

    best_score = 0.0
    for text in ocr_texts:
        if not text:
            continue
        score = fuzz.partial_ratio(form_name.lower(), text.lower())
        if score > best_score:
            best_score = score

    return best_score if best_score > 0 else None


def _check_dob(dob: date, ocr_texts: list) -> bool:
    """
    Searches OCR text for the applicant's date of birth in common formats:
    DD/MM/YYYY, DD-MM-YYYY, D Month YYYY (e.g. 5 January 1990)
    Returns True if any match is found across all provided OCR texts.
    """
    if not dob:
        return False

    MONTH_NAMES = {
        1: ['january', 'jan'],
        2: ['february', 'feb'],
        3: ['march', 'mar'],
        4: ['april', 'apr'],
        5: ['may'],
        6: ['june', 'jun'],
        7: ['july', 'jul'],
        8: ['august', 'aug'],
        9: ['september', 'sep', 'sept'],
        10: ['october', 'oct'],
        11: ['november', 'nov'],
        12: ['december', 'dec'],
    }

    patterns_to_search = [
        f"{dob.day:02d}/{dob.month:02d}/{dob.year}",
        f"{dob.day:02d}-{dob.month:02d}-{dob.year}",
        f"{dob.day}/{dob.month}/{dob.year}",
        f"{dob.day}-{dob.month}-{dob.year}",
    ]
    # Add month name variants
    for abbr in MONTH_NAMES.get(dob.month, []):
        patterns_to_search.append(f"{dob.day} {abbr} {dob.year}")
        patterns_to_search.append(f"{dob.day:02d} {abbr} {dob.year}")

    for text in ocr_texts:
        text_lower = text.lower()
        for pattern in patterns_to_search:
            if pattern.lower() in text_lower:
                return True

    return False
