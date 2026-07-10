import json
import random
from decimal import Decimal

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import User
from apps.core.models import EmailOTP


def _format_price_lakhs(value):
    try:
        return f"{Decimal(value or 0) / Decimal('100000'):.2f} Lakhs"
    except Exception:
        return "0.00 Lakhs"

def portal_selection(request):
    """Renders the glassmorphic portal picker page."""
    if request.user.is_authenticated:
        if request.user.role == User.BUYER:
            return redirect('buyer_dashboard')
        elif request.user.role == User.ADMIN or request.user.is_superuser:
            return redirect('admin_dashboard')
    return render(request, 'accounts/portal_selection.html')

def buyer_login(request):
    """Handles authentication checks for the Buyer Portal."""
    if request.user.is_authenticated:
        if request.user.role == User.BUYER:
            return redirect('buyer_dashboard')
        logout(request) # Log out other roles before logging in as Buyer

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please provide both username/email/phone and password.')
            return render(request, 'accounts/buyer_login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role == User.BUYER:
                if user.status == User.ACTIVE:
                    login(request, user)
                    return redirect('buyer_dashboard')
                elif user.status == User.PENDING:
                    messages.error(request, 'Your buyer profile status is pending administrative approval.')
                else:
                    messages.error(request, 'Your buyer profile has been suspended.')
            else:
                messages.error(request, 'Invalid credentials for the Buyer portal.')
        else:
            messages.error(request, 'Invalid login credentials.')

    return render(request, 'accounts/buyer_login.html')

@login_required(login_url='portal_selection')
def buyer_dashboard(request):
    """Displays the Buyer Portal Dashboard if role matches."""
    if request.user.role != User.BUYER:
        # If user is superuser admin, we let them view it for debugging, otherwise deny
        if not request.user.is_superuser:
            raise PermissionDenied("You do not have access to this portal.")
            
    from apps.core.models import Notification, PurchaseRequest
    from apps.lands.models import SavedPlot
    
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    
    purchase_requests = PurchaseRequest.objects.filter(buyer=request.user).select_related('land', 'land__owner').order_by('-created_at')
    purchased_plots = purchase_requests.filter(status='approved')
    purchased_count = purchased_plots.count()
    
    saved_plots = SavedPlot.objects.filter(user=request.user).select_related('land').order_by('-created_at')
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'purchase_requests': purchase_requests,
        'purchased_plots': purchased_plots,
        'purchased_count': purchased_count,
        'saved_plots': saved_plots,
    }
            
    return render(request, 'accounts/buyer_dashboard.html', context)

def logout_view(request):
    """Logs out the user and redirects to the landing selection portal."""
    logout(request)
    return redirect('portal_selection')

def landowner_login(request):
    """Handles authentication checks for the Land Owner Portal."""
    if request.user.is_authenticated:
        if request.user.role == User.LAND_OWNER:
            return redirect('landowner_dashboard')
        logout(request)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please provide both username/email/phone and password.')
            return render(request, 'accounts/landowner_login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role == User.LAND_OWNER:
                if user.status == User.ACTIVE:
                    login(request, user)
                    return redirect('landowner_dashboard')
                elif user.status == User.PENDING:
                    messages.error(request, 'Your landowner profile status is pending administrative approval.')
                else:
                    messages.error(request, 'Your landowner profile has been suspended.')
            else:
                messages.error(request, 'Invalid credentials for the Land Owner portal.')
        else:
            messages.error(request, 'Invalid login credentials.')

    return render(request, 'accounts/landowner_login.html')

def admin_login(request):
    """Handles authentication checks for the Admin Portal."""
    if request.user.is_authenticated:
        if request.user.role == User.ADMIN or request.user.is_superuser:
            return redirect('admin_dashboard')
        logout(request)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please provide both username and password.')
            return render(request, 'accounts/admin_login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role == User.ADMIN or user.is_superuser:
                login(request, user)
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Invalid credentials for the Admin portal.')
        else:
            messages.error(request, 'Invalid login credentials.')

    return render(request, 'accounts/admin_login.html')

@login_required(login_url='portal_selection')
def landowner_dashboard(request):
    """Displays the Land Owner Portal Dashboard — shows only this owner's lands and their notifications."""
    if request.user.role != User.LAND_OWNER:
        if not request.user.is_superuser:
            raise PermissionDenied("You do not have access to this portal.")

    from apps.lands.models import Land
    from apps.core.models import Notification, PurchaseRequest

    lands = list(Land.objects.filter(owner=request.user).prefetch_related('plots', 'images'))
    for land in lands:
        land.display_location = land.location or '-'
        land.display_plot_price_lakhs = _format_price_lakhs(land.average_plot_price)
    notifications = Notification.objects.filter(recipient=request.user)
    unread_count  = notifications.filter(is_read=False).count()
    sent_requests = Notification.objects.filter(
        sender=request.user,
        notif_type__in=['land_delete_request', 'plot_delete_request']
    ).order_by('-created_at')
    
    purchase_requests = PurchaseRequest.objects.filter(
        land__owner=request.user
    ).select_related('buyer', 'land').order_by('-created_at')

    pending_purchase_count = purchase_requests.filter(
        status__in=['pending', 'meeting_scheduled']
    ).count()

    active_buyers = purchase_requests.filter(status='approved')

    context = {
        'lands': lands,
        'notifications': notifications,
        'unread_count': unread_count,
        'sent_requests': sent_requests,
        'purchase_requests': purchase_requests,
        'pending_purchase_count': pending_purchase_count,
        'active_buyers': active_buyers,
    }
    return render(request, 'accounts/landowner_dashboard.html', context)


@login_required(login_url='portal_selection')
def admin_dashboard(request):
    """Displays the Admin Portal Dashboard if role matches."""
    if request.user.role != User.ADMIN:
        if not request.user.is_superuser:
            raise PermissionDenied("You do not have access to this portal.")

    from apps.lands.models import Land
    from apps.core.models import Notification

    # Auto-discard draft lands that never progressed past boundary plotting.
    for land in Land.objects.select_related('owner').all():
        has_boundary = bool(land.boundary_coordinates and len(land.boundary_coordinates) >= 3)
        if not has_boundary and not land.plots.exists() and not land.roads.exists() and not land.points.exists():
            land.delete()

    lands = list(Land.objects.select_related('owner').all())
    for land in lands:
        land.display_location = land.location or '-'
        land.display_plot_price_lakhs = _format_price_lakhs(land.average_plot_price)
    landowners = User.objects.filter(role=User.LAND_OWNER)
    notifications = Notification.objects.filter(recipient=request.user)
    unread_count  = notifications.filter(is_read=False).count()

    context = {
        'lands': lands,
        'landowners': landowners,
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'accounts/admin_dashboard.html', context)


def _process_profile_post(request, user, section):
    """Shared POST handler for buyer and landowner profiles."""
    action = request.POST.get('action', 'update_profile')

    if action == 'update_profile':
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.phone_number = request.POST.get('phone_number', '').strip()
        user.address = request.POST.get('address', '').strip() or None
        user.city = request.POST.get('city', '').strip() or None
        user.state = request.POST.get('state', '').strip() or None
        user.country = request.POST.get('country', '').strip() or None

        photo_updated = False
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
            photo_updated = True

        user.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if photo_updated and user.profile_picture:
                return JsonResponse({'status': 'done', 'profile_picture_url': user.profile_picture.url})
            return JsonResponse({'status': 'done'})

        messages.success(request, 'Profile updated successfully.')
        return redirect(request.path + f'?section={section}')

    elif action == 'remove_photo':
        if user.profile_picture:
            user.profile_picture.delete(save=False)
            user.profile_picture = None
            user.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'done', 'message': 'Profile photo removed.'})

        messages.success(request, 'Profile photo removed.')
        return redirect(request.path + f'?section={section}')

    return None


def _process_preferences_post(request, user):
    """Handles updating UserPreferences."""
    from decimal import Decimal, InvalidOperation
    from apps.accounts.models import UserPreferences

    prefs, _ = UserPreferences.objects.get_or_create(user=user)

    min_budget_str = request.POST.get('min_budget', '').strip()
    max_budget_str = request.POST.get('max_budget', '').strip()
    min_acres_str = request.POST.get('min_acres', '').strip()
    max_acres_str = request.POST.get('max_acres', '').strip()
    property_condition = request.POST.get('property_condition', 'no_preference').strip()
    
    proximity_preferences = request.POST.getlist('proximity_preferences')

    min_budget = None
    max_budget = None
    min_acres = None
    max_acres = None

    errors = {}

    if min_budget_str:
        try:
            min_budget = Decimal(min_budget_str)
            if min_budget < 0:
                errors['min_budget'] = "Minimum budget cannot be negative."
        except (InvalidOperation, ValueError):
            errors['min_budget'] = "Invalid minimum budget value."

    if max_budget_str:
        try:
            max_budget = Decimal(max_budget_str)
            if max_budget < 0:
                errors['max_budget'] = "Maximum budget cannot be negative."
        except (InvalidOperation, ValueError):
            errors['max_budget'] = "Invalid maximum budget value."

    if min_acres_str:
        try:
            min_acres = Decimal(min_acres_str)
            if min_acres < 0:
                errors['min_acres'] = "Minimum acres cannot be negative."
        except (InvalidOperation, ValueError):
            errors['min_acres'] = "Invalid minimum acres value."

    if max_acres_str:
        try:
            max_acres = Decimal(max_acres_str)
            if max_acres < 0:
                errors['max_acres'] = "Maximum acres cannot be negative."
        except (InvalidOperation, ValueError):
            errors['max_acres'] = "Invalid maximum acres value."

    if not errors:
        if min_budget is not None and max_budget is not None and min_budget > max_budget:
            errors['min_budget'] = "Minimum budget cannot exceed maximum budget."
        if min_acres is not None and max_acres is not None and min_acres > max_acres:
            errors['min_acres'] = "Minimum acres cannot exceed maximum acres."

    if errors:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'errors': errors}, status=400)
        for field, msg in errors.items():
            messages.error(request, msg)
        return None

    # Save preferences
    prefs.min_budget = min_budget
    prefs.max_budget = max_budget
    prefs.min_acres = min_acres
    prefs.max_acres = max_acres
    prefs.property_condition = property_condition
    prefs.proximity_preferences = proximity_preferences
    prefs.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'done', 'message': 'Preferences updated successfully.'})

    messages.success(request, 'Preferences updated successfully.')
    return None


@login_required
def profile(request):
    user = request.user
    section = request.GET.get('section', 'personal')
    
    from apps.accounts.models import UserPreferences
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        if section == 'preferences':
            result = _process_preferences_post(request, user)
            if result:
                return result
            return redirect(request.path + '?section=preferences')
        else:
            result = _process_profile_post(request, user, section)
            if result:
                return result
    return render(request, 'accounts/profile.html', {
        'active_section': section,
        'preferences': prefs,
    })


@login_required
def landowner_profile(request):
    user = request.user
    section = request.GET.get('section', 'personal')
    if request.method == 'POST':
        result = _process_profile_post(request, user, section)
        if result:
            return result
    return render(request, 'accounts/landowner_profile.html', {
        'active_section': section,
    })


@login_required
def preferences(request):
    from django.urls import reverse
    if request.user.role == 'LAND_OWNER':
        return redirect(reverse('landowner_profile'))
    return redirect(reverse('profile') + '?section=preferences')


@login_required
def send_profile_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        purpose = data.get('purpose', '')  # 'change_email' or 'change_password'

        if not email:
            return JsonResponse({'error': 'Email is required.'}, status=400)

        # Enforce 1-minute wait
        last_otp = EmailOTP.objects.filter(email=email).order_by('-created_at').first()
        if last_otp:
            time_diff = (timezone.now() - last_otp.created_at).total_seconds()
            if time_diff < 60:
                wait_time = int(60 - time_diff)
                return JsonResponse({'error': f'Please wait {wait_time} seconds before requesting another OTP.'}, status=400)

        otp = f"{random.randint(100000, 999999)}"
        EmailOTP.objects.create(email=email, otp_code=otp)

        subject = '[Lease Monkey] OTP for Account Update'
        message = (
            f'Hello,\n\n'
            f'Your OTP for {"email change" if purpose == "change_email" else "password change"} is: {otp}\n\n'
            f'This OTP is valid for 5 minutes.\n\n'
            f'— The Lease Monkey Team'
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=False,
        )

        return JsonResponse({'status': 'sent', 'message': 'OTP sent successfully.'})
    except Exception as e:
        return JsonResponse({'error': f'Failed to send OTP. {str(e)}'}, status=500)


@login_required
def verify_profile_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        otp = data.get('otp', '').strip()
        purpose = data.get('purpose', '')

        if not email or not otp:
            return JsonResponse({'error': 'Email and OTP are required.'}, status=400)

        otp_record = EmailOTP.objects.filter(email=email, otp_code=otp, is_used=False).first()
        if not otp_record:
            return JsonResponse({'error': 'Incorrect OTP.'}, status=400)
        if otp_record.is_expired():
            return JsonResponse({'error': 'OTP expired. Please request a new one.'}, status=400)

        otp_record.is_used = True
        otp_record.save()

        user = request.user

        if purpose == 'change_email':
            user.email = email
            user.save()
            return JsonResponse({'status': 'done', 'message': 'Email updated successfully.'})

        elif purpose == 'change_password':
            new_password = data.get('new_password', '')
            if len(new_password) < 8:
                return JsonResponse({'error': 'Password must be at least 8 characters.'}, status=400)
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)
            return JsonResponse({'status': 'done', 'message': 'Password updated successfully.'})

        return JsonResponse({'status': 'verified', 'message': 'OTP verified successfully.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
