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
from apps.accounts.utils import (
    validate_password_strength,
    calculate_age,
    parse_indian_number,
    format_indian_numeral
)


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
                    if not user.is_verified:
                        # Send fresh OTP and redirect to verification
                        otp = f"{random.randint(100000, 999999)}"
                        EmailOTP.objects.create(email=user.email, otp_code=otp)
                        try:
                            send_mail(
                                subject='[Lease Monkey] Verify Your Email Address',
                                message=f'Welcome back! Verify your account using OTP: {otp}\n\nThis OTP is valid for 5 minutes.\n\n— The Lease Monkey Team',
                                from_email=settings.EMAIL_HOST_USER,
                                recipient_list=[user.email],
                                fail_silently=True,
                            )
                        except Exception:
                            pass
                        request.session['verify_email_addr'] = user.email
                        messages.warning(request, 'Please verify your email address to log in. A new OTP has been sent.')
                        return redirect('verify_email')
                    
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
            
    from apps.core.models import Notification, PurchaseRequest, Ticket
    from apps.lands.models import SavedPlot
    
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    
    purchase_requests = PurchaseRequest.objects.filter(buyer=request.user, land__is_live=True).select_related('land', 'land__owner').order_by('-created_at')
    purchased_plots = purchase_requests.filter(status='approved')
    purchased_count = purchased_plots.count()
    
    saved_plots = SavedPlot.objects.filter(user=request.user, land__is_live=True).select_related('land').order_by('-created_at')
    
    tickets = Ticket.objects.filter(user=request.user).order_by('-created_at')
    faqs = [
        {'question': 'How long does verification take?',
         'answer': 'Verification typically takes 2-3 business days after submitting all required documents. You will be notified via email once the verification is complete.'},
        {'question': 'How are plots approved?',
         'answer': 'Plots are approved after the landowner and buyer complete a scheduled meeting. The landowner can then approve the purchase request from their dashboard.'},
        {'question': 'How do meetings work?',
         'answer': 'Meetings are scheduled through the platform. Once a purchase request is submitted, the landowner can schedule a meeting with the buyer. Both parties receive the meeting link and reminders.'},
        {'question': 'How do I update my profile?',
         'answer': 'You can update your profile by clicking on "Profile" in the sidebar navigation. From there, you can edit your personal information, contact details, and preferences.'},
        {'question': 'Can I cancel a purchase request?',
         'answer': 'Yes, you can cancel a purchase request while it is still in "Pending" status. Contact support if you need assistance with an already-processed request.'},
    ]
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'purchase_requests': purchase_requests,
        'purchased_plots': purchased_plots,
        'purchased_count': purchased_count,
        'saved_plots': saved_plots,
        'tickets': tickets,
        'faqs': faqs,
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

    # Redirect to onboarding if first login
    if request.user.role == User.LAND_OWNER and request.user.is_first_login:
        return redirect('onboarding_landowner')

    from apps.lands.models import Land, OccupancyRecord, LandRegistrationRequest
    from apps.core.models import Notification, PurchaseRequest, Ticket

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

    occupancy_records = OccupancyRecord.objects.filter(
        land__owner=request.user
    ).select_related('buyer', 'land').order_by('-allotted_at')

    # Get land registration requests
    land_requests = LandRegistrationRequest.objects.filter(owner=request.user).order_by('-submitted_at')

    landowner_tickets = Ticket.objects.filter(user=request.user).order_by('-created_at')
    faqs = [
        {'question': 'How long does verification take?',
         'answer': 'Verification typically takes 2-3 business days after submitting all required documents. You will be notified via email once the verification is complete.'},
        {'question': 'How are plots approved?',
         'answer': 'Plots are approved after the landowner and buyer complete a scheduled meeting. The landowner can then approve the purchase request from their dashboard.'},
        {'question': 'How do meetings work?',
         'answer': 'Meetings are scheduled through the platform. Once a purchase request is submitted, the landowner can schedule a meeting with the buyer. Both parties receive the meeting link and reminders.'},
        {'question': 'How do I update my profile?',
         'answer': 'You can update your profile by clicking on "Profile" in the sidebar navigation. From there, you can edit your personal information, contact details, and preferences.'},
        {'question': 'Can I cancel a purchase request?',
         'answer': 'Yes, you can cancel a purchase request while it is still in "Pending" status. Contact support if you need assistance with an already-processed request.'},
    ]

    context = {
        'lands': lands,
        'notifications': notifications,
        'unread_count': unread_count,
        'sent_requests': sent_requests,
        'purchase_requests': purchase_requests,
        'pending_purchase_count': pending_purchase_count,
        'active_buyers': active_buyers,
        'occupancy_records': occupancy_records,
        'land_requests': land_requests,
        'landowner_tickets': landowner_tickets,
        'faqs': faqs,
    }
    return render(request, 'accounts/landowner_dashboard.html', context)


@login_required(login_url='portal_selection')
def admin_dashboard(request):
    """Displays the Admin Portal Dashboard if role matches."""
    if request.user.role != User.ADMIN:
        if not request.user.is_superuser:
            raise PermissionDenied("You do not have access to this portal.")

    from apps.lands.models import Land, LandRegistrationRequest
    from apps.core.models import Notification

    # Auto-discard draft lands that never progressed past boundary plotting, unless linked to a request
    for land in Land.objects.select_related('owner').all():
        has_boundary = bool(land.boundary_coordinates and len(land.boundary_coordinates) >= 3)
        has_request = hasattr(land, 'registration_request')
        if not has_boundary and not land.plots.exists() and not land.roads.exists() and not land.points.exists():
            if not has_request:
                land.delete()

    lands = list(Land.objects.select_related('owner').all())
    for land in lands:
        land.display_location = land.location or '-'
        land.display_plot_price_lakhs = _format_price_lakhs(land.average_plot_price)
    landowners = User.objects.filter(role=User.LAND_OWNER)
    buyers = User.objects.filter(role=User.BUYER)
    notifications = Notification.objects.filter(recipient=request.user)
    unread_count  = notifications.filter(is_read=False).count()

    from apps.ai.models import SupportTicket
    from apps.core.models import Ticket
    from apps.accounts.models import LandownerApplication
    tickets = SupportTicket.objects.all().order_by('-created_at')
    support_tickets = Ticket.objects.select_related('user').all().order_by('-created_at')
    open_tickets_count = support_tickets.filter(status='open').count()
    landowner_applications = LandownerApplication.objects.all().order_by('-created_at')
    land_requests = LandRegistrationRequest.objects.all().order_by('-submitted_at')
    pending_requests_count = land_requests.filter(status='pending').count()

    context = {
        'lands': lands,
        'landowners': landowners,
        'buyers': buyers,
        'notifications': notifications,
        'unread_count': unread_count,
        'tickets': tickets,
        'support_tickets': support_tickets,
        'open_tickets_count': open_tickets_count,
        'landowner_applications': landowner_applications,
        'land_requests': land_requests,
        'pending_requests_count': pending_requests_count,
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


def buyer_register(request):
    """Handles Buyer Registration POST requests and tab display state."""
    from datetime import datetime, timedelta
    import re

    # GET request — show login page with register tab active
    if request.method == 'GET':
        return render(request, 'accounts/buyer_login.html', {
            'active_tab': 'register',
        })

    # Execute unverified user accounts purge (1 hour cleanup guard)
    try:
        purge_time = timezone.now() - timedelta(hours=1)
        User.objects.filter(is_verified=False, created_at__lt=purge_time).delete()
    except Exception:
        pass

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        dob_str = request.POST.get('dob', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        phone_country_code = request.POST.get('phone_country_code', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # Gather any validation errors
        errors = []

        if not (email and first_name and dob_str and phone_number and username and password and confirm_password):
            errors.append("All fields are required.")

        # Email check
        if email and User.objects.filter(email__iexact=email).exists():
            errors.append("An account with this email already exists.")

        # Username check
        if username and User.objects.filter(username__iexact=username).exists():
            errors.append("This username is already taken.")

        # Confirm password check
        if password != confirm_password:
            errors.append("Passwords do not match.")

        # Password strength validation
        pw_errors = validate_password_strength(password)
        errors.extend(pw_errors)

        # DOB Age check (>= 18)
        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                if calculate_age(dob) < 18:
                    errors.append("You must be at least 18 years old to register.")
            except ValueError:
                errors.append("Invalid date of birth format.")

        # Phone uniqueness check
        full_phone = f"{phone_country_code}{phone_number}"
        full_phone = re.sub(r'[\s\-]', '', full_phone)
        if phone_number and User.objects.filter(phone_number=full_phone).exists():
            errors.append("An account with this phone number already exists.")

        if errors:
            for err in errors:
                messages.error(request, err)
            # Re-render login card showing the registration form active
            return render(request, 'accounts/buyer_login.html', {
                'active_tab': 'register',
                'reg_email': email,
                'reg_name': first_name,
                'reg_dob': dob_str,
                'reg_phone': phone_number,
                'reg_username': username,
            })

        # Save user to DB as unverified
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                date_of_birth=dob,
                phone_number=full_phone,
                role=User.BUYER,
                status=User.ACTIVE,
                is_verified=False
            )
            
            # Create OTP
            otp = f"{random.randint(100000, 999999)}"
            EmailOTP.objects.create(email=email, otp_code=otp)
            
            # Send Email
            send_mail(
                subject='[Lease Monkey] Verify Your Email Address',
                message=(
                    f'Hello {first_name},\n\n'
                    f'Thank you for registering with Lease Monkey. Your email verification OTP is:\n\n'
                    f'🔑 {otp}\n\n'
                    f'This OTP is valid for 5 minutes. If you do not verify your email within 1 hour, your account details will be removed.\n\n'
                    f'— The Lease Monkey Team'
                ),
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=True,
            )
            
            # Set email in session to identify verify target
            request.session['verify_email_addr'] = email
            messages.success(request, 'Registration details saved. Please check your email for verification OTP.')
            return redirect('verify_email')
        except Exception as e:
            messages.error(request, f"Error saving account: {e}")
            return render(request, 'accounts/buyer_login.html', {'active_tab': 'register'})

    return redirect('buyer_login')


def verify_email(request):
    """Renders OTP verification page and processes OTP submissions."""
    email = request.session.get('verify_email_addr')
    if not email:
        messages.error(request, "No registration session found. Please sign up again.")
        return redirect('buyer_login')

    if request.method == 'POST':
        otp_submitted = request.POST.get('otp', '').strip()
        
        # Check database
        record = EmailOTP.objects.filter(email=email, is_used=False).order_by('-created_at').first()
        
        if not record:
            messages.error(request, "No verification request found for this email.")
            return render(request, 'accounts/verify_email.html')
            
        if record.is_expired():
            messages.error(request, "The verification code has expired. Please log in to request a new OTP.")
            return render(request, 'accounts/verify_email.html')
            
        if record.otp_code != otp_submitted:
            messages.error(request, "Invalid verification code.")
            return render(request, 'accounts/verify_email.html')
            
        # Success!
        record.is_used = True
        record.save()
        
        # Update User
        try:
            user = User.objects.get(email=email)
            user.is_verified = True
            user.save()
            
            # Authenticate and log in user
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Redirect to preferences onboarding wizard
            messages.success(request, "Email verified successfully! Let's set up your preferences.")
            return redirect('onboarding_preferences')
        except User.DoesNotExist:
            messages.error(request, "Associated user account was not found.")
            return redirect('buyer_login')

    return render(request, 'accounts/verify_email.html')


@login_required(login_url='portal_selection')
def onboarding_preferences(request):
    """Buyer onboarding flow wizard to set up search preferences, or skip to defaults."""
    if request.user.role != User.BUYER:
        return redirect('portal_selection')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Get or create preferences
        from apps.accounts.models import UserPreferences
        prefs, created = UserPreferences.objects.get_or_create(user=request.user)
        
        if action == 'skip':
            # Skip and apply default preferences: min=0, max=10 Lakhs (10,00,000 INR)
            prefs.min_budget = Decimal('0')
            prefs.max_budget = Decimal('1000000') # 10 Lakhs
            prefs.min_acres = None
            prefs.max_acres = None
            prefs.property_condition = 'no_preference'
            prefs.proximity_preferences = []
            prefs.save()
            messages.info(request, "Proceeding with default preferences.")
            return redirect('buyer_dashboard')
            
        # Standard save action
        min_budget_str = request.POST.get('min_budget', '').strip()
        max_budget_str = request.POST.get('max_budget', '').strip()
        min_acres = request.POST.get('min_acres', '').strip()
        max_acres = request.POST.get('max_acres', '').strip()
        property_condition = request.POST.get('property_condition', 'no_preference')
        proximity_list = request.POST.getlist('proximity_preferences')
        
        # Parse budgets using Indian format parser helper
        min_budget = parse_indian_number(min_budget_str)
        max_budget = parse_indian_number(max_budget_str)
        
        # Validate budget ranges
        if min_budget is not None and max_budget is not None and min_budget > max_budget:
            messages.error(request, "Minimum budget cannot exceed Maximum budget.")
            return render(request, 'accounts/onboarding_preferences.html')
            
        # Parse acres
        try:
            min_a = Decimal(min_acres) if min_acres else None
            max_a = Decimal(max_acres) if max_acres else None
            if min_a is not None and max_a is not None and min_a > max_a:
                messages.error(request, "Minimum acres cannot exceed Maximum acres.")
                return render(request, 'accounts/onboarding_preferences.html')
            prefs.min_acres = min_a
            prefs.max_acres = max_a
        except Exception:
            messages.error(request, "Invalid numerical format for acres fields.")
            return render(request, 'accounts/onboarding_preferences.html')
            
        prefs.min_budget = min_budget
        prefs.max_budget = max_budget
        prefs.property_condition = property_condition
        prefs.proximity_preferences = proximity_list
        prefs.save()
        
        messages.success(request, "Onboarding completed! Preferences saved successfully.")
        return redirect('buyer_dashboard')
        
    return render(request, 'accounts/onboarding_preferences.html')


def forgot_password(request):
    """Processes password recovery email verification requests and triggers reset OTPs."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, "Please enter your email address.")
            return render(request, 'accounts/forgot_password.html')
            
        # Look up registered buyer account
        user = User.objects.filter(email=email, role=User.BUYER, is_verified=True).first()
        
        if not user:
            messages.error(request, "No registered buyer profile matches this email address.")
            return render(request, 'accounts/forgot_password.html')
            
        # Generate OTP
        otp = f"{random.randint(100000, 999999)}"
        EmailOTP.objects.create(email=email, otp_code=otp)
        
        # Send mail
        try:
            send_mail(
                subject='[Lease Monkey] Password Reset Request Verification Code',
                message=(
                    f'Hello {user.first_name or user.username},\n\n'
                    f'We received a request to reset your password. Use the verification code below to process the change:\n\n'
                    f'🔑 {otp}\n\n'
                    f'This code is valid for 5 minutes.\n\n'
                    f'— The Lease Monkey Team'
                ),
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception:
            pass
            
        request.session['reset_password_email'] = email
        messages.success(request, "A password reset code has been sent to your email.")
        return redirect('forgot_password_reset')
        
    return render(request, 'accounts/forgot_password.html')


def forgot_password_reset(request):
    """Validates the reset OTP and updates the user's password."""
    email = request.session.get('reset_password_email')
    if not email:
        messages.error(request, "Reset session has expired. Please request another code.")
        return redirect('forgot_password')
        
    if request.method == 'POST':
        otp_submitted = request.POST.get('otp', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        errors = []
        if not (otp_submitted and new_password and confirm_password):
            errors.append("All fields are required.")
            
        if new_password != confirm_password:
            errors.append("Passwords do not match.")
            
        pw_errors = validate_password_strength(new_password)
        errors.extend(pw_errors)
        
        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'accounts/forgot_password_reset.html')
            
        # Check OTP
        record = EmailOTP.objects.filter(email=email, is_used=False).order_by('-created_at').first()
        if not record:
            messages.error(request, "No active reset request found for this email.")
            return render(request, 'accounts/forgot_password_reset.html')
            
        if record.is_expired():
            messages.error(request, "Verification code has expired.")
            return render(request, 'accounts/forgot_password_reset.html')
            
        if record.otp_code != otp_submitted:
            messages.error(request, "Invalid verification code.")
            return render(request, 'accounts/forgot_password_reset.html')
            
        # All valid! Update password
        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            
            # Clear session
            record.is_used = True
            record.save()
            request.session.pop('reset_password_email', None)
            
            messages.success(request, "Password updated successfully. Please log in with your new credentials.")
            return redirect('buyer_login')
        except User.DoesNotExist:
            messages.error(request, "Associated user account was not found.")
            return redirect('buyer_login')
            
    return render(request, 'accounts/forgot_password_reset.html')


@login_required
def send_delete_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        user = request.user
        # Enforce 1-minute wait before resending
        last_otp = EmailOTP.objects.filter(email=user.email).order_by('-created_at').first()
        if last_otp:
            time_diff = (timezone.now() - last_otp.created_at).total_seconds()
            if time_diff < 60:
                wait_time = int(60 - time_diff)
                return JsonResponse({'error': f'Please wait {wait_time} seconds before requesting another OTP.'}, status=400)
        
        otp = f"{random.randint(100000, 999999)}"
        EmailOTP.objects.create(email=user.email, otp_code=otp)
        
        send_mail(
            subject='[Lease Monkey] OTP to Delete Your Account',
            message=(
                f'Hello {user.first_name or user.username},\n\n'
                f'We received a request to permanently delete your Lease Monkey account. '
                f'Your verification OTP is:\n\n'
                f'🔑 {otp}\n\n'
                f'This OTP is valid for 5 minutes. If you did not request this, please secure your account immediately.\n\n'
                f'— The Lease Monkey Team'
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return JsonResponse({'status': 'sent', 'message': 'OTP sent to your registered email.'})
    except Exception as e:
        return JsonResponse({'error': f'Failed to send OTP: {e}'}, status=500)


@login_required
def delete_account(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        otp = data.get('otp', '').strip()
        
        if not username or not otp:
            return JsonResponse({'error': 'Username and OTP are required.'}, status=400)
            
        if username != request.user.username:
            return JsonResponse({'error': 'Username confirmation does not match.'}, status=400)
            
        # Verify OTP
        otp_record = EmailOTP.objects.filter(email=request.user.email, otp_code=otp, is_used=False).first()
        if not otp_record:
            return JsonResponse({'error': 'Incorrect OTP.'}, status=400)
        if otp_record.is_expired():
            return JsonResponse({'error': 'OTP has expired.'}, status=400)
            
        # OTP is correct! Mark used and delete user
        otp_record.is_used = True
        otp_record.save()
        
        user = request.user
        logout(request)
        user.delete()
        
        return JsonResponse({'status': 'deleted', 'message': 'Your account has been deleted successfully.'})
    except Exception as e:
        return JsonResponse({'error': f'Failed to delete account: {e}'}, status=500)


@login_required
def admin_delete_buyer(request, username):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
        
    if request.user.role != User.ADMIN and not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied.'}, status=403)
        
    try:
        buyer = User.objects.filter(username=username, role=User.BUYER).first()
        if not buyer:
            return JsonResponse({'error': 'Buyer not found.'}, status=404)
        buyer.delete()
        return JsonResponse({'status': 'deleted', 'message': f'Buyer account {username} deleted successfully.'})
    except Exception as e:
        return JsonResponse({'error': f'Failed to delete buyer: {e}'}, status=500)


# ---------------------------------------------------------------------------
# Landowner Registration Wizard (multi-step, session-backed)
# ---------------------------------------------------------------------------

import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.files import File
from apps.accounts.models import LandownerApplication
from apps.core.models import Notification
from datetime import datetime


def _lo_wizard_data(request):
    return request.session.setdefault('lo_reg_data', {})


def landowner_register_step1(request):
    """Personal Information: first_name, last_name, date_of_birth, mobile_number, email"""
    lo_data = _lo_wizard_data(request)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        date_of_birth = request.POST.get('date_of_birth', '').strip()
        mobile_number = request.POST.get('mobile_number', '').strip()
        email = request.POST.get('email', '').strip()

        errors = []
        if not all([first_name, last_name, date_of_birth, mobile_number, email]):
            errors.append('All fields are required.')
        if date_of_birth:
            try:
                dob = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
                age = (timezone.now().date() - dob).days // 365
                if age < 18:
                    errors.append('You must be at least 18 years old.')
            except ValueError:
                errors.append('Invalid date of birth format.')
        if email and User.objects.filter(email__iexact=email).exists():
            errors.append('An account with this email already exists.')
        if mobile_number and len(mobile_number) < 10:
            errors.append('Invalid mobile number.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/landowner_register.html', {
                'step': 1,
                'data': request.POST,
            })

        lo_data.update({
            'first_name': first_name,
            'last_name': last_name,
            'date_of_birth': date_of_birth,
            'mobile_number': mobile_number,
            'email': email,
        })
        request.session['lo_reg_data'] = lo_data
        return redirect('landowner_register_step2')

    return render(request, 'accounts/landowner_register.html', {
        'step': 1,
        'data': lo_data,
    })


def landowner_register_step2(request):
    """Government Information: aadhaar_number, pan_number"""
    lo_data = _lo_wizard_data(request)
    if not lo_data.get('email'):
        messages.warning(request, 'Please start from step 1.')
        return redirect('landowner_register_step1')

    if request.method == 'POST':
        aadhaar_number = request.POST.get('aadhaar_number', '').strip()
        pan_number = request.POST.get('pan_number', '').strip()

        errors = []
        if not aadhaar_number or not pan_number:
            errors.append('All fields are required.')
        if aadhaar_number and len(aadhaar_number) != 12:
            errors.append('Aadhaar number must be exactly 12 digits.')
        if aadhaar_number and not aadhaar_number.isdigit():
            errors.append('Aadhaar number must contain only digits.')
        if pan_number and len(pan_number) != 10:
            errors.append('PAN number must be exactly 10 characters.')
        if LandownerApplication.objects.filter(aadhaar_number=aadhaar_number).exclude(status='REJECTED').exists():
            errors.append('This Aadhaar number has already been used in a pending or approved application.')
        if LandownerApplication.objects.filter(pan_number=pan_number).exclude(status='REJECTED').exists():
            errors.append('This PAN number has already been used in a pending or approved application.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/landowner_register.html', {
                'step': 2,
                'data': {**lo_data, **request.POST},
            })

        lo_data.update({
            'aadhaar_number': aadhaar_number,
            'pan_number': pan_number.upper(),
        })
        request.session['lo_reg_data'] = lo_data
        return redirect('landowner_register_step3')

    return render(request, 'accounts/landowner_register.html', {
        'step': 2,
        'data': lo_data,
    })


def landowner_register_step3(request):
    """Land Information: land_name, land_address, state, district, pincode, total_area, ownership_details"""
    lo_data = _lo_wizard_data(request)
    if not lo_data.get('pan_number'):
        messages.warning(request, 'Please complete step 2 first.')
        return redirect('landowner_register_step2')

    if request.method == 'POST':
        land_name = request.POST.get('land_name', '').strip()
        land_address = request.POST.get('land_address', '').strip()
        state = request.POST.get('state', '').strip()
        district = request.POST.get('district', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        total_area = request.POST.get('total_area', '').strip()
        ownership_details = request.POST.get('ownership_details', '').strip()

        errors = []
        if not all([land_name, land_address, state, district, pincode, total_area, ownership_details]):
            errors.append('All fields are required.')
        if pincode and (len(pincode) != 6 or not pincode.isdigit()):
            errors.append('Pincode must be a 6-digit number.')
        if total_area:
            try:
                area = float(total_area)
                if area <= 0:
                    errors.append('Total area must be greater than zero.')
            except ValueError:
                errors.append('Invalid total area value.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/landowner_register.html', {
                'step': 3,
                'data': {**lo_data, **request.POST},
            })

        lo_data.update({
            'land_name': land_name,
            'land_address': land_address,
            'state': state,
            'district': district,
            'pincode': pincode,
            'total_area': total_area,
            'ownership_details': ownership_details,
        })
        request.session['lo_reg_data'] = lo_data
        return redirect('landowner_register_step4')

    return render(request, 'accounts/landowner_register.html', {
        'step': 3,
        'data': lo_data,
    })


def landowner_register_step4(request):
    """Document Upload: aadhaar_document, pan_document, ownership_document"""
    lo_data = _lo_wizard_data(request)
    if not lo_data.get('total_area'):
        messages.warning(request, 'Please complete step 3 first.')
        return redirect('landowner_register_step3')

    if request.method == 'POST':
        aadhaar_file = request.FILES.get('aadhaar_document')
        pan_file = request.FILES.get('pan_document')
        ownership_file = request.FILES.get('ownership_document')

        errors = []
        if not aadhaar_file:
            errors.append('Aadhaar document is required.')
        if not pan_file:
            errors.append('PAN document is required.')
        if not ownership_file:
            errors.append('Ownership document is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/landowner_register.html', {
                'step': 4,
                'data': lo_data,
            })

        # Save to temp location with session key prefix
        session_key = request.session.session_key or 'nosession'
        for field_name, f in [('aadhaar_document', aadhaar_file), ('pan_document', pan_file), ('ownership_document', ownership_file)]:
            ext = os.path.splitext(f.name)[1] or ''
            temp_name = f'{field_name}_{session_key}{ext}'
            temp_path = default_storage.save(f'temp_lo_app/{session_key}/{temp_name}', ContentFile(f.read()))
            lo_data[f'{field_name}_path'] = temp_path
            lo_data[f'{field_name}_name'] = f.name

        request.session['lo_reg_data'] = lo_data
        return redirect('landowner_register_send_otp')

    return render(request, 'accounts/landowner_register.html', {
        'step': 4,
        'data': lo_data,
    })


def landowner_register_send_otp(request):
    """Send OTP for email verification (step 5)."""
    lo_data = _lo_wizard_data(request)
    email = lo_data.get('email')
    if not email:
        messages.warning(request, 'Session expired. Please start again.')
        return redirect('landowner_register_step1')

    # Enforce 1-minute resend cooldown
    last_otp = EmailOTP.objects.filter(email=email).order_by('-created_at').first()
    if last_otp:
        time_diff = (timezone.now() - last_otp.created_at).total_seconds()
        if time_diff < 60:
            wait_time = int(60 - time_diff)
            messages.warning(request, f'Please wait {wait_time} seconds before requesting another OTP.')
            return render(request, 'accounts/landowner_register.html', {'step': 5, 'data': lo_data, 'otp_sent': True})

    otp = f"{random.randint(100000, 999999)}"
    EmailOTP.objects.create(email=email, otp_code=otp)

    send_mail(
        subject='[Lease Monkey] Verify Your Email – Landowner Registration',
        message=(
            f'Hello {lo_data.get("first_name", "")},\n\n'
            f'Thank you for registering as a Landowner with Lease Monkey.\n'
            f'Your email verification OTP is:\n\n'
            f'{otp}\n\n'
            f'This OTP is valid for 5 minutes.\n\n'
            f'— The Lease Monkey Team'
        ),
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        fail_silently=True,
    )

    messages.success(request, 'An OTP has been sent to your email.')
    return render(request, 'accounts/landowner_register.html', {
        'step': 5,
        'data': lo_data,
        'otp_sent': True,
    })


def landowner_register_verify_otp(request):
    """Verify OTP for email verification."""
    lo_data = _lo_wizard_data(request)
    email = lo_data.get('email')
    if not email:
        messages.warning(request, 'Session expired. Please start again.')
        return redirect('landowner_register_step1')

    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()

        if not otp:
            messages.error(request, 'Please enter the OTP.')
            return render(request, 'accounts/landowner_register.html', {'step': 5, 'data': lo_data, 'otp_sent': True})

        record = EmailOTP.objects.filter(email=email, otp_code=otp, is_used=False).order_by('-created_at').first()
        if not record:
            messages.error(request, 'Invalid OTP.')
            return render(request, 'accounts/landowner_register.html', {'step': 5, 'data': lo_data, 'otp_sent': True})
        if record.is_expired():
            messages.error(request, 'OTP has expired. Please request a new one.')
            return render(request, 'accounts/landowner_register.html', {'step': 5, 'data': lo_data, 'otp_sent': True})

        record.is_used = True
        record.save()

        lo_data['email_verified'] = True
        request.session['lo_reg_data'] = lo_data
        messages.success(request, 'Email verified successfully!')
        return redirect('landowner_register_review')

    return render(request, 'accounts/landowner_register.html', {
        'step': 5,
        'data': lo_data,
        'otp_sent': True,
    })


def landowner_register_review(request):
    """Review all data before final submission."""
    lo_data = _lo_wizard_data(request)
    if not lo_data.get('email_verified'):
        messages.warning(request, 'Please verify your email first.')
        return redirect('landowner_register_send_otp')

    return render(request, 'accounts/landowner_register.html', {
        'step': 6,
        'data': lo_data,
    })


def landowner_register_submit(request):
    """Final submission — create LandownerApplication record."""
    from django.urls import reverse
    lo_data = _lo_wizard_data(request)
    if not lo_data.get('email_verified'):
        messages.warning(request, 'Please verify your email first.')
        return redirect('landowner_register_send_otp')

    if request.method != 'POST':
        return redirect('landowner_register_review')

    # Check for duplicate application from same email
    existing = LandownerApplication.objects.filter(
        email=lo_data['email']
    ).exclude(status='REJECTED').first()
    if existing:
        messages.error(request, 'You already have a pending or approved application.')
        return redirect('landowner_register_review')

    app = LandownerApplication(
        first_name=lo_data['first_name'],
        last_name=lo_data['last_name'],
        date_of_birth=datetime.strptime(lo_data['date_of_birth'], '%Y-%m-%d').date(),
        mobile_number=lo_data['mobile_number'],
        email=lo_data['email'],
        aadhaar_number=lo_data['aadhaar_number'],
        pan_number=lo_data['pan_number'],
        land_name=lo_data['land_name'],
        land_address=lo_data['land_address'],
        state=lo_data['state'],
        district=lo_data['district'],
        pincode=lo_data['pincode'],
        total_area=lo_data['total_area'],
        ownership_details=lo_data['ownership_details'],
        email_verified=True,
    )
    app.save()

    # Move uploaded files from temp to the model's FileField
    session_key = request.session.session_key or 'nosession'
    for field_name in ['aadhaar_document', 'pan_document', 'ownership_document']:
        temp_path = lo_data.get(f'{field_name}_path')
        orig_name = lo_data.get(f'{field_name}_name', field_name)
        if temp_path and default_storage.exists(temp_path):
            with default_storage.open(temp_path) as f:
                getattr(app, field_name).save(orig_name, File(f))
            default_storage.delete(temp_path)
    app.save(update_fields=['aadhaar_document', 'pan_document', 'ownership_document'])

    # Cleanup session
    request.session.pop('lo_reg_data', None)

    # --- Trigger async OCR validation (non-blocking) ---
    import threading
    from apps.accounts.models import OCRValidation
    from apps.accounts.ocr_pipeline import run_ocr_validation
    OCRValidation.objects.create(application=app, validation_status='pending')
    ocr_thread = threading.Thread(target=run_ocr_validation, args=(app.pk,), daemon=True)
    ocr_thread.start()

    # Notify all admin users (in-app + email)
    admin_users = User.objects.filter(role=User.ADMIN)
    for admin in admin_users:
        Notification.objects.create(
            recipient=admin,
            sender=None,
            notif_type='lo_registration_request',
            title='New Landowner Registration Request',
            message=f'{app.first_name} {app.last_name} ({app.email}) has submitted a landowner registration application.',
            landowner_application=app,
        )
    # Also send email to all admin users
    admin_emails = list(admin_users.values_list('email', flat=True))
    if admin_emails:
        detail_url = request.build_absolute_uri(
            reverse('admin_landowner_application_detail', args=[app.pk])
        )
        send_mail(
            subject='[Lease Monkey] New Landowner Registration Received',
            message=(
                f'A new landowner registration application has been received.\n\n'
                f'Applicant: {app.first_name} {app.last_name}\n'
                f'Email: {app.email}\n'
                f'Phone: {app.mobile_number}\n'
                f'Land Name: {app.land_name}\n'
                f'Submitted: {app.created_at.strftime("%d %b %Y at %H:%M")}\n\n'
                f'Review this application: {detail_url}\n\n'
                f'— The Lease Monkey System'
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=admin_emails,
            fail_silently=True,
        )

    # Send confirmation email to applicant
    send_mail(
        subject='[Lease Monkey] Landowner Application Submitted',
        message=(
            f'Dear {app.first_name},\n\n'
            f'Your landowner registration application has been submitted successfully.\n'
            f'Application ID: #{app.pk}\n\n'
            f'Our team will review your application and notify you of the decision.\n'
            f'This process typically takes 2-3 business days.\n\n'
            f'— The Lease Monkey Team'
        ),
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[app.email],
        fail_silently=True,
    )

    return redirect('landowner_register_success')


def landowner_register_success(request):
    return render(request, 'accounts/landowner_register.html', {
        'step': 'done',
    })


# ---------------------------------------------------------------------------
# Admin Review Views
# ---------------------------------------------------------------------------

def _ensure_admin(request):
    if request.user.role != User.ADMIN and not request.user.is_superuser:
        raise PermissionDenied("You do not have access to this section.")


@login_required
def admin_landowner_applications(request):
    _ensure_admin(request)
    status_filter = request.GET.get('status', '')
    risk_filter   = request.GET.get('risk', '')
    apps_qs = LandownerApplication.objects.select_related('ocr_validation').all()

    if status_filter:
        apps_qs = apps_qs.filter(status=status_filter)
    if risk_filter:
        if risk_filter == 'failed':
            apps_qs = apps_qs.filter(ocr_validation__validation_status='failed')
        else:
            apps_qs = apps_qs.filter(ocr_validation__risk_level=risk_filter)

    return render(request, 'accounts/admin_landowner_applications.html', {
        'applications': apps_qs,
        'current_status': status_filter,
        'current_risk': risk_filter,
        'status_choices': LandownerApplication.APPLICATION_STATUS,
    })


@login_required
def admin_landowner_application_detail(request, app_id):
    _ensure_admin(request)
    try:
        app = LandownerApplication.objects.get(pk=app_id)
    except LandownerApplication.DoesNotExist:
        messages.error(request, 'Application not found.')
        return redirect('admin_landowner_applications')

    ocr = getattr(app, 'ocr_validation', None)
    return render(request, 'accounts/admin_landowner_application_detail.html', {
        'app': app,
        'ocr': ocr,
    })


@login_required
def admin_landowner_approve(request, app_id):
    _ensure_admin(request)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)

    try:
        app = LandownerApplication.objects.get(pk=app_id)
    except LandownerApplication.DoesNotExist:
        return JsonResponse({'error': 'Application not found.'}, status=404)

    if app.status not in ('PENDING', 'UNDER_REVIEW'):
        return JsonResponse({'error': f'Application is already {app.get_status_display()}.'}, status=400)

    remarks = request.POST.get('admin_remarks', '').strip()
    app.admin_remarks = remarks
    user, password = app.approve(admin_user=request.user)

    # Notify applicant
    Notification.objects.create(
        recipient=user,
        sender=request.user,
        notif_type='lo_registration_approved',
        title='Landowner Registration Approved',
        message=(
            f'Dear {app.first_name}, your landowner registration has been approved!\n'
            f'Username: {user.username}\n'
            f'Please log in and change your password.'
        ),
        landowner_application=app,
    )

    # Send email with credentials
    send_mail(
        subject='[Lease Monkey] Landowner Registration Approved',
        message=(
            f'Dear {app.first_name},\n\n'
            f'Congratulations! Your landowner registration has been approved.\n\n'
            f'Application ID: #{app.pk}\n'
            f'Your login credentials:\n'
            f'Username: {user.username}\n'
            f'Password: {password}\n\n'
            f'Please log in at: {request.build_absolute_uri("/")}accounts/login/landowner/\n\n'
            f'We recommend changing your password after your first login.\n\n'
            f'— The Lease Monkey Team'
        ),
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[app.email],
        fail_silently=True,
    )

    messages.success(request, f'Application #{app.pk} approved. User "{user.username}" created.')
    return redirect('admin_landowner_applications')


@login_required
def admin_landowner_reject(request, app_id):
    _ensure_admin(request)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)

    try:
        app = LandownerApplication.objects.get(pk=app_id)
    except LandownerApplication.DoesNotExist:
        return JsonResponse({'error': 'Application not found.'}, status=404)

    if app.status not in ('PENDING', 'UNDER_REVIEW'):
        return JsonResponse({'error': f'Application is already {app.get_status_display()}.'}, status=400)

    reason = request.POST.get('rejection_reason', '').strip()
    if not reason:
        return JsonResponse({'error': 'Rejection reason is required.'}, status=400)

    app.reject(admin_user=request.user, reason=reason)

    send_mail(
        subject='[Lease Monkey] Landowner Registration Update',
        message=(
            f'Dear {app.first_name},\n\n'
            f'Thank you for your interest in registering as a Landowner with Lease Monkey.\n\n'
            f'After reviewing your application (ID: #{app.pk}), we regret to inform you that it has been rejected.\n\n'
            f'Reason: {reason}\n\n'
            f'If you believe this decision was made in error, please contact our support team.\n\n'
            f'— The Lease Monkey Team'
        ),
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[app.email],
        fail_silently=True,
    )

    messages.success(request, f'Application #{app.pk} rejected.')
    return redirect('admin_landowner_applications')


@login_required(login_url='portal_selection')
def onboarding_landowner(request):
    """Handles first-time login onboarding welcome for landowners."""
    if request.user.role != User.LAND_OWNER:
        raise PermissionDenied("Only landowners can complete landowner onboarding.")

    if request.method == 'POST' or request.GET.get('action') == 'skip':
        request.user.is_first_login = False
        request.user.save(update_fields=['is_first_login'])
        messages.success(request, "Welcome to Lease Monkey! You can now register your properties.")
        return redirect('landowner_dashboard')

    return render(request, 'accounts/onboarding_landowner.html')


@login_required
def admin_delete_landowner(request, username):
    """Allows administrators to hard-delete registered landowner accounts."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
        
    if request.user.role != User.ADMIN and not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied.'}, status=403)
        
    try:
        landowner = User.objects.filter(username=username, role=User.LAND_OWNER).first()
        if not landowner:
            return JsonResponse({'error': 'Landowner not found.'}, status=404)
        
        landowner_name = landowner.get_full_name() or username
        landowner.delete()
        return JsonResponse({'status': 'deleted', 'message': f'Landowner account for {landowner_name} deleted successfully.'})
    except Exception as e:
        return JsonResponse({'error': f'Failed to delete landowner: {e}'}, status=500)


