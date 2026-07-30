import json
import requests
import uuid
import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.contrib import messages

from apps.lands.models import Land, LandRegistrationRequest
from apps.core.models import Notification
from apps.accounts.models import User
from .models import LandSubscription, PaymentTransaction


def get_cashfree_headers():
    return {
        'x-client-id': settings.CASHFREE_CLIENT_ID,
        'x-client-secret': settings.CASHFREE_CLIENT_SECRET_KEY,
        'x-api-version': getattr(settings, 'CASHFREE_API_VERSION', '2023-08-01'),
        'Content-Type': 'application/json',
    }


def get_cashfree_base_url():
    env = getattr(settings, 'CASHFREE_ENVIRONMENT', 'SANDBOX').upper()
    if env in ['PRODUCTION', 'PROD']:
        return 'https://api.cashfree.com/pg'
    return 'https://sandbox.cashfree.com/pg'


def notify_admin_payment_received(land, landowner, amount):
    """Notify all admins that a landowner has paid; admin now needs to digitize and publish."""
    admins = User.objects.filter(role=User.ADMIN)
    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            sender=landowner,
            notif_type='system',
            title="💳 Hosting Payment Received — Digitize & Publish Required",
            message=(
                f"{landowner.get_full_name() or landowner.username} has paid ₹{amount} "
                f"hosting fee for '{land.name}'. Please trace the plot layout in the Creator "
                f"and publish the land live. Go to Admin > Land Requests to proceed."
            )
        )


def check_and_send_expiry_notifications():
    """
    Send renewal reminders 5 days before subscription expiry.
    Called by management commands and daily scheduler.
    """
    now = timezone.now()
    five_days_later = now + datetime.timedelta(days=5)

    expiring_subs = LandSubscription.objects.filter(
        status='active',
        end_date__gte=now,
        end_date__lte=five_days_later
    ).select_related('land', 'user')

    for sub in expiring_subs:
        days_left = max(0, (sub.end_date - now).days)
        title = f"⏰ Hosting Subscription Expiring in {days_left} Day{'s' if days_left != 1 else ''}"
        message = (
            f"Your hosting subscription for '{sub.land.name}' expires on "
            f"{sub.end_date.strftime('%d %b %Y')}. Renew now from your Payments tab "
            f"to keep your property live and visible to buyers."
        )

        # Skip if we already sent this exact notification within 24h
        already_sent = Notification.objects.filter(
            recipient=sub.user,
            title=title,
            created_at__gte=now - datetime.timedelta(hours=24)
        ).exists()

        if not already_sent:
            Notification.objects.create(
                recipient=sub.user,
                notif_type='system',
                title=title,
                message=message
            )


def check_and_expire_subscriptions():
    """
    Checks active subscriptions whose end_date has passed.
    Marks status='expired', takes the land offline (is_live=False), and notifies owner.
    """
    now = timezone.now()
    expired_subs = LandSubscription.objects.filter(
        status='active',
        end_date__lt=now
    ).select_related('land', 'user')

    for sub in expired_subs:
        sub.status = 'expired'
        sub.save(update_fields=['status'])

        if sub.land and sub.land.is_live:
            sub.land.is_live = False
            sub.land.save(update_fields=['is_live'])

        title = "🔴 Hosting Subscription Expired — Land Taken Offline"
        message = (
            f"Your hosting subscription for '{sub.land.name}' expired on "
            f"{sub.end_date.strftime('%d %b %Y')}. The land has been automatically "
            f"taken offline. Renew now from your Payments tab to reactivate it."
        )

        already_sent = Notification.objects.filter(
            recipient=sub.user,
            title=title,
            created_at__gte=now - datetime.timedelta(hours=24)
        ).exists()

        if not already_sent:
            Notification.objects.create(
                recipient=sub.user,
                notif_type='system',
                title=title,
                message=message
            )


def activate_or_renew_subscription(sub):
    """
    Activates or renews a LandSubscription according to rules:
    - If active & not expired (end_date >= now): Extend end_date by 30 days from existing end_date.
    - If expired/inactive (end_date < now or status != 'active'):
      Set start_date = now (payment date), end_date = now + 30 days, status = 'active'.
      Automatically reactivates land to live (is_live = True).
    """
    now = timezone.now()
    if sub.status == 'active' and sub.end_date and sub.end_date >= now:
        sub.end_date = sub.end_date + datetime.timedelta(days=30)
    else:
        sub.start_date = now
        sub.end_date = now + datetime.timedelta(days=30)
        sub.status = 'active'
        if sub.land and not sub.land.is_live:
            sub.land.is_live = True
            sub.land.save(update_fields=['is_live'])

    sub.status = 'active'
    sub.save()
    return sub


# ─── Cashfree Order Creation ──────────────────────────────────────────────────

@login_required
@require_POST
def create_cashfree_order(request, slug):
    """
    Creates a Cashfree Sandbox order for ₹200/month hosting fee + 18% GST = ₹236.
    Returns payment_session_id to trigger Cashfree JS SDK checkout.
    """
    land = get_object_or_404(Land, slug=slug)

    amount = 236.00  # ₹200 + 18% GST
    order_id = f"order_lm_{uuid.uuid4().hex[:12]}"
    cust_id = f"cust_{request.user.pk}"
    cust_name = request.user.get_full_name() or request.user.username
    cust_email = request.user.email or f"{request.user.username}@leasemonkey.com"
    cust_phone = getattr(request.user, 'phone_number', '') or "9999999999"

    return_url = (
        request.build_absolute_uri(reverse('payments:cashfree_return'))
        + f"?order_id={order_id}&slug={slug}"
    )

    payload = {
        "order_amount": amount,
        "order_currency": "INR",
        "order_id": order_id,
        "customer_details": {
            "customer_id": cust_id,
            "customer_name": cust_name,
            "customer_email": cust_email,
            "customer_phone": cust_phone
        },
        "order_meta": {"return_url": return_url}
    }

    try:
        res = requests.post(
            f"{get_cashfree_base_url()}/orders",
            headers=get_cashfree_headers(),
            json=payload,
            timeout=10
        )
        res_data = res.json()

        if res.status_code in [200, 201] and 'payment_session_id' in res_data:
            payment_session_id = res_data['payment_session_id']
            now = timezone.now()
            sub, _ = LandSubscription.objects.get_or_create(
                land=land, user=request.user,
                defaults={
                    'amount': 200.00, 'status': 'pending',
                    'start_date': now,
                    'end_date': now + datetime.timedelta(days=30)
                }
            )
            PaymentTransaction.objects.create(
                subscription=sub, user=request.user,
                transaction_id=order_id, order_id=order_id,
                payment_session_id=payment_session_id,
                amount=amount, payment_method='Cashfree Sandbox', status='pending'
            )
            return JsonResponse({
                'success': True,
                'payment_session_id': payment_session_id,
                'order_id': order_id,
                'environment': getattr(settings, 'CASHFREE_ENVIRONMENT', 'SANDBOX').lower()
            })
        else:
            return JsonResponse({'success': False, 'error': res_data.get('message', 'Failed to create order.')}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Connection error: {str(e)}"}, status=500)


# ─── Cashfree Return (Post-Payment Redirect) ──────────────────────────────────

@login_required
def cashfree_return(request):
    """
    Cashfree redirects here after checkout. Verifies payment via REST API.
    On success: activates subscription and notifies admin to digitize & publish.
    NOTE: Admin makes land live — NOT this function.
    """
    order_id = request.GET.get('order_id')
    slug = request.GET.get('slug')

    if not order_id:
        messages.error(request, "Invalid payment reference.")
        return redirect('landowner_dashboard')

    try:
        res = requests.get(
            f"{get_cashfree_base_url()}/orders/{order_id}",
            headers=get_cashfree_headers(),
            timeout=10
        )
        res_data = res.json()

        if res.status_code == 200 and res_data.get('order_status') == 'PAID':
            tx = PaymentTransaction.objects.filter(order_id=order_id).first()
            if tx:
                tx.status = 'success'
                tx.save()

                sub = activate_or_renew_subscription(tx.subscription)
                land = sub.land
                # Update registration request to show payment received, awaiting admin
                req = LandRegistrationRequest.objects.filter(land=land).first()
                if req and req.status == 'payment_pending':
                    req.status = 'payment_completed'
                    req.save(update_fields=['status'])

                notify_admin_payment_received(land, request.user, tx.amount)

                messages.success(
                    request,
                    f"✅ Payment successful for '{land.name}'! Admin has been notified to digitize your plot layout and publish it live."
                )
            else:
                messages.success(request, "Payment received! Admin has been notified.")
            return redirect('/accounts/landowner/dashboard/?payment=success#payments')
        else:
            order_status = res_data.get('order_status', 'PENDING')
            messages.warning(request, f"Payment not yet complete. Status: {order_status}. Please try again from your Payments tab.")
            return redirect('/accounts/landowner/dashboard/#payments')
    except Exception as e:
        messages.error(request, f"Error verifying payment: {str(e)}")
        return redirect('landowner_dashboard')


# ─── Cashfree Webhook (Server-to-Server) ──────────────────────────────────────

@csrf_exempt
def cashfree_webhook(request):
    """Server-to-server webhook from Cashfree for async payment confirmations."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        data = json.loads(request.body)
        event_type = data.get('type')

        if event_type == 'PAYMENT_SUCCESS_WEBHOOK':
            order_id = data.get('data', {}).get('order', {}).get('order_id')
            if order_id:
                tx = PaymentTransaction.objects.filter(order_id=order_id).first()
                if tx and tx.status != 'success':
                    tx.status = 'success'
                    tx.save()
                    sub = activate_or_renew_subscription(tx.subscription)
                    land = sub.land
                    req = LandRegistrationRequest.objects.filter(land=land).first()
                    if req and req.status == 'payment_pending':
                        req.status = 'payment_completed'
                        req.save(update_fields=['status'])
                    notify_admin_payment_received(land, tx.user, tx.amount)

        return HttpResponse(status=200)
    except Exception:
        return HttpResponse(status=400)


# ─── Demo / Fallback Payment (Simulated) ──────────────────────────────────────

@login_required
@require_POST
def process_demo_payment(request, slug):
    """
    Simulated payment for testing (fallback when Cashfree gateway is unreachable).
    """
    land = get_object_or_404(Land, slug=slug)
    now = timezone.now()

    sub, created = LandSubscription.objects.get_or_create(
        land=land, user=request.user,
        defaults={
            'amount': 200.00, 'status': 'active',
            'start_date': now, 'end_date': now + datetime.timedelta(days=30)
        }
    )
    sub = activate_or_renew_subscription(sub)

    tx = PaymentTransaction.objects.create(
        subscription=sub, user=request.user,
        transaction_id=f"LM-PAY-{uuid.uuid4().hex[:8].upper()}",
        order_id=f"demo_{uuid.uuid4().hex[:10]}",
        amount=236.00,
        payment_method=request.POST.get('payMethod', 'Cashfree Sandbox'),
        status='success'
    )

    # Update registration request status
    req = LandRegistrationRequest.objects.filter(land=land).first()
    if req and req.status == 'payment_pending':
        req.status = 'payment_completed'
        req.save(update_fields=['status'])

    notify_admin_payment_received(land, request.user, tx.amount)

    return JsonResponse({
        'success': True,
        'transaction_id': tx.transaction_id,
        'land_name': land.name,
        'amount': str(tx.amount),
        'end_date': sub.end_date.strftime('%d %b %Y'),
        'message': 'Payment received! Admin has been notified to digitize and publish your land.'
    })
