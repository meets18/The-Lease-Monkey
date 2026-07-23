import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from .models import Notification


from django.shortcuts import redirect, render
from apps.lands.models import Land, SavedPlot, Plot
from apps.core.models import PurchaseRequest, Notification


class LandingPageView(TemplateView):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            user = request.user
            if user.role == 'ADMIN' or user.is_superuser:
                return redirect('admin_dashboard')
            elif user.role == 'BUYER':
                context = self.get_buyer_context(user)
                return render(request, 'buyer_landing.html', context)
            elif user.role == 'LAND_OWNER':
                context = self.get_landowner_context(user)
                return render(request, 'landowner_landing.html', context)
        return render(request, 'landing.html', {})

    def get_buyer_context(self, user):
        active_requests = PurchaseRequest.objects.filter(buyer=user).select_related('land').order_by('-created_at')[:4]
        saved_plots = SavedPlot.objects.filter(user=user, land__is_live=True).select_related('land').order_by('-created_at')[:4]
        recent_notifs = Notification.objects.filter(recipient=user).order_by('-created_at')[:5]
        unread_notifs_count = Notification.objects.filter(recipient=user, is_read=False).count()

        # Preference-based land recommendations
        try:
            prefs = user.preferences
            lands_qs = Land.objects.filter(is_live=True).prefetch_related('images', 'plots')
            if prefs.min_budget:
                lands_qs = lands_qs.filter(average_plot_price__gte=prefs.min_budget)
            if prefs.max_budget:
                lands_qs = lands_qs.filter(average_plot_price__lte=prefs.max_budget)
            recommended_lands = lands_qs.order_by('-created_at')[:6]
            # Fallback: if no matches after filtering, show latest
            if not recommended_lands.exists():
                recommended_lands = Land.objects.filter(is_live=True).order_by('-created_at')[:6]
        except Exception:
            recommended_lands = Land.objects.filter(is_live=True).order_by('-created_at')[:6]

        return {
            'active_requests': active_requests,
            'saved_plots': saved_plots,
            'recommended_lands': recommended_lands,
            'recent_notifs': recent_notifs,
            'unread_notifs_count': unread_notifs_count,
            'total_saved_count': SavedPlot.objects.filter(user=user, land__is_live=True).count(),
            'total_requests_count': PurchaseRequest.objects.filter(buyer=user).count(),
        }

    def get_landowner_context(self, user):
        my_lands = Land.objects.filter(owner=user).order_by('-created_at')
        my_requests = PurchaseRequest.objects.filter(land__owner=user).select_related('land')
        pending_requests = my_requests.filter(status__in=['pending', 'meeting_scheduled'])
        scheduled_meetings = my_requests.filter(status='meeting_scheduled', meeting_datetime__isnull=False).order_by('meeting_datetime')[:4]
        recent_notifs = Notification.objects.filter(recipient=user).order_by('-created_at')[:5]
        unread_notifs_count = Notification.objects.filter(recipient=user, is_read=False).count()

        total_plots_count = Plot.objects.filter(land__owner=user).count()
        sold_plots_count = Plot.objects.filter(land__owner=user, status='sold').count()

        return {
            'my_lands': my_lands[:4],
            'total_lands_count': my_lands.count(),
            'total_plots_count': total_plots_count,
            'sold_plots_count': sold_plots_count,
            'pending_requests': pending_requests[:5],
            'pending_requests_count': pending_requests.count(),
            'scheduled_meetings': scheduled_meetings,
            'recent_notifs': recent_notifs,
            'unread_notifs_count': unread_notifs_count,
        }


import re


@csrf_exempt
def submit_contact(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        data = json.loads(request.body) if request.body else {}
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()

        errors = []
        if not name:
            errors.append('Name is required.')
        if not email:
            errors.append('Email is required.')
        elif not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Invalid email address.')
        if not subject:
            errors.append('Subject is required.')
        if not message:
            errors.append('Message is required.')

        if errors:
            return JsonResponse({'error': '; '.join(errors)}, status=400)

        full_message = (
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Subject: {subject}\n"
            f"Message:\n{message}\n"
        )
        send_mail(
            subject=f'[Lease Monkey Contact] {subject}',
            message=full_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=['the1leasemonkey@gmail.com'],
            fail_silently=False,
        )
        return JsonResponse({'status': 'sent', 'message': 'Thank you for contacting us! We will get back to you shortly.'})
    except Exception as e:
        return JsonResponse({'error': f'Failed to send message: {str(e)}'}, status=500)


class PrivacyPolicyView(TemplateView):
    template_name = "core/privacy.html"


class TermsOfServiceView(TemplateView):
    template_name = "core/terms.html"


@login_required
def handle_notification_action(request, notification_id):
    """
    Admin endpoint to approve or reject a deletion request.
    POST body: { "action": "approve"|"reject", "rejection_message": "..." }
    """
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method.'}, status=400)

    try:
        notif = Notification.objects.get(id=notification_id, recipient=request.user)
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found.'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    action = data.get('action', '').strip()

    if action == 'approve':
        return _handle_approve(request, notif)
    elif action == 'reject':
        rejection_message = data.get('rejection_message', '').strip()
        if not rejection_message:
            return JsonResponse({'error': 'A rejection message is required.'}, status=400)
        return _handle_reject(request, notif, rejection_message)
    else:
        return JsonResponse({'error': 'Invalid action. Use "approve" or "reject".'}, status=400)


def _handle_approve(request, notif):
    """Hard-delete the requested land or plot and notify the landowner."""
    from apps.lands.models import Land, Plot, Building

    landowner = notif.sender
    land_name = '(unknown)'
    item_label = '(unknown)'

    try:
        from apps.core.models import PurchaseRequest
        if notif.notif_type == 'land_delete_request':
            land = Land.objects.get(slug=notif.land_slug)
            land_name = land.name
            item_label = f"Land: {land_name}"
            if PurchaseRequest.objects.filter(land=land, status__in=['approved', 'lease_active']).exists():
                return JsonResponse({'error': 'Cannot approve deletion. Some plots are allotted to buyers. Please de-allot them first.'}, status=400)
            land.delete()

        elif notif.notif_type == 'plot_delete_request':
            land = Land.objects.get(slug=notif.land_slug)
            land_name = land.name
            plot_num = notif.plot_number
            kind = notif.plot_kind or 'plot'
            if kind == 'building':
                obj = land.buildings.filter(building_id=plot_num).first()
                item_label = f"Building {plot_num} in {land_name}"
            else:
                obj = land.plots.filter(plot_number=plot_num).first()
                item_label = f"Plot {plot_num} in {land_name}"
                if PurchaseRequest.objects.filter(land=land, plot_number=plot_num, status__in=['approved', 'lease_active']).exists():
                    return JsonResponse({'error': 'Cannot approve deletion. This plot is allotted to a buyer. Please de-allot them first.'}, status=400)
            if obj:
                obj.delete()
            else:
                return JsonResponse({'error': 'Item not found. It may have already been deleted.'}, status=404)
        else:
            return JsonResponse({'error': 'Cannot approve this notification type.'}, status=400)

    except Land.DoesNotExist:
        return JsonResponse({'error': 'Land not found. It may have already been deleted.'}, status=404)

    # Mark original notification as read
    notif.is_read = True
    notif.save()

    # Create in-app notification for the landowner
    if landowner:
        Notification.objects.create(
            recipient=landowner,
            sender=request.user,
            notif_type='request_approved',
            title=f"Deletion Approved: {item_label}",
            message=(
                f"Your deletion request for '{item_label}' has been approved by the admin. "
                f"The item has been permanently removed from the system."
            ),
            land_slug=notif.land_slug,
            plot_number=notif.plot_number,
        )

        # Send approval/rejection email to landowner
        landowner_email = settings.LANDOWNER_EMAIL or landowner.email
        if landowner_email:
            try:
                send_mail(
                    subject=f"[Lease Monkey] Deletion Approved — {item_label}",
                    message=(
                        f"Hello {landowner.username},\n\n"
                        f"Your deletion request for '{item_label}' has been approved by the admin.\n"
                        f"The item has been permanently removed from the system.\n\n"
                        f"— The Lease Monkey Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[landowner_email],
                    fail_silently=True,
                )
            except Exception:
                pass  # Don't let email failure block the response

    return JsonResponse({'status': 'approved', 'item': item_label})


def _handle_reject(request, notif, rejection_message):
    """Send a rejection message back to the landowner via in-app + email."""
    landowner = notif.sender

    if notif.notif_type == 'land_delete_request':
        item_label = f"Land deletion request (slug: {notif.land_slug})"
    elif notif.notif_type == 'plot_delete_request':
        item_label = f"Plot {notif.plot_number} deletion request"
    else:
        item_label = "Your deletion request"

    # Mark original notification as read
    notif.is_read = True
    notif.save()

    # Create in-app notification for the landowner
    if landowner:
        Notification.objects.create(
            recipient=landowner,
            sender=request.user,
            notif_type='request_rejected',
            title=f"Deletion Request Rejected",
            message=f"Your request to delete '{item_label}' was rejected by the admin.\n\nReason: {rejection_message}",
            land_slug=notif.land_slug,
            plot_number=notif.plot_number,
        )

        # Send rejection email to landowner
        landowner_email = settings.LANDOWNER_EMAIL or landowner.email
        if landowner_email:
            try:
                send_mail(
                    subject=f"[Lease Monkey] Deletion Request Rejected",
                    message=(
                        f"Hello {landowner.username},\n\n"
                        f"Your deletion request for '{item_label}' has been reviewed and rejected by the admin.\n\n"
                        f"Admin's message:\n{rejection_message}\n\n"
                        f"If you believe this is an error, please contact the administrator.\n\n"
                        f"— The Lease Monkey Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[landowner_email],
                    fail_silently=True,
                )
            except Exception:
                pass

    return JsonResponse({'status': 'rejected', 'item': item_label})


@login_required
def mark_notification_read(request, notification_id):
    """Marks a notification as read for the current user."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        notif = Notification.objects.get(id=notification_id, recipient=request.user)
        notif.is_read = True
        notif.save()
        return JsonResponse({'status': 'ok'})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Not found.'}, status=404)

@login_required
def delete_notification(request, notification_id):
    """Deletes a notification for the current user."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        notif = Notification.objects.get(id=notification_id, recipient=request.user)
        notif.delete()
        return JsonResponse({'status': 'ok'})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Not found.'}, status=404)


import os
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404


from django.views.decorators.clickjacking import xframe_options_exempt


@login_required
@xframe_options_exempt
def serve_protected_file(request, model_name, pk):
    """
    Serve protected files after permission check.
    Prevents direct access to media URLs for sensitive documents.

    model_name: 'ticket' | 'ticket_reply' | 'identity' | 'layout'
    """
    file_path = None
    original_name = None

    if model_name == 'ticket':
        from .models import Ticket
        obj = get_object_or_404(Ticket, id=pk)
        if obj.user != request.user and request.user.role != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied()
        file_path = obj.attachment.path if obj.attachment else None
        original_name = f'ticket_{obj.ticket_id}_attachment{os.path.splitext(obj.attachment.name)[1] if obj.attachment else ""}'

    elif model_name == 'ticket_reply':
        from .models import TicketReply
        obj = get_object_or_404(TicketReply, id=pk)
        if obj.ticket.user != request.user and request.user.role != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied()
        file_path = obj.attachment.path if obj.attachment else None
        original_name = f'reply_{obj.id}_attachment{os.path.splitext(obj.attachment.name)[1] if obj.attachment else ""}'

    elif model_name == 'identity':
        from apps.accounts.models import LandownerApplication
        obj = get_object_or_404(LandownerApplication, id=pk)
        if request.user.role != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied()
        doc_field = request.GET.get('doc', '')
        if doc_field == 'aadhaar':
            file_path = obj.aadhaar_document.path if obj.aadhaar_document else None
            original_name = f'aadhaar_{obj.first_name}_{obj.last_name}{os.path.splitext(obj.aadhaar_document.name)[1] if obj.aadhaar_document else ""}'
        elif doc_field == 'pan':
            file_path = obj.pan_document.path if obj.pan_document else None
            original_name = f'pan_{obj.first_name}_{obj.last_name}{os.path.splitext(obj.pan_document.name)[1] if obj.pan_document else ""}'
        elif doc_field == 'ownership':
            file_path = obj.ownership_document.path if obj.ownership_document else None
            original_name = f'ownership_{obj.first_name}_{obj.last_name}{os.path.splitext(obj.ownership_document.name)[1] if obj.ownership_document else ""}'
        else:
            return JsonResponse({'error': 'Invalid document field. Use ?doc=aadhaar|pan|ownership'}, status=400)

    elif model_name == 'land_request':
        from apps.lands.models import LandRegistrationRequest
        obj = get_object_or_404(LandRegistrationRequest, id=pk)
        if obj.owner != request.user and request.user.role != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied()
        doc_field = request.GET.get('doc', '')
        if doc_field == 'ownership':
            file_path = obj.ownership_proof.path if obj.ownership_proof else None
            original_name = f'ownership_{obj.property_name}{os.path.splitext(obj.ownership_proof.name)[1] if obj.ownership_proof else ""}'
        elif doc_field == 'floor_plan':
            file_path = obj.floor_plan.path if obj.floor_plan else None
            original_name = f'floor_plan_{obj.property_name}{os.path.splitext(obj.floor_plan.name)[1] if obj.floor_plan else ""}'
        elif doc_field == 'registry_sale_deed':
            file_path = obj.registry_sale_deed.path if obj.registry_sale_deed else None
            original_name = f'registry_deed_{obj.property_name}{os.path.splitext(obj.registry_sale_deed.name)[1] if obj.registry_sale_deed else ""}'
        elif doc_field == 'supporting_docs':
            file_path = obj.supporting_documents.path if obj.supporting_documents else None
            original_name = f'supporting_docs_{obj.property_name}{os.path.splitext(obj.supporting_documents.name)[1] if obj.supporting_documents else ""}'
        elif doc_field == 'pricing_csv':
            file_path = obj.plot_pricing_csv.path if obj.plot_pricing_csv else None
            original_name = f'pricing_csv_{obj.property_name}{os.path.splitext(obj.plot_pricing_csv.name)[1] if obj.plot_pricing_csv else ""}'
        else:
            return JsonResponse({'error': 'Invalid document field. Use ?doc=ownership|floor_plan|registry_sale_deed|supporting_docs|pricing_csv'}, status=400)

    else:
        raise Http404('Invalid file type.')

    if not file_path or not os.path.exists(file_path):
        raise Http404('File not found.')

    response = FileResponse(open(file_path, 'rb'))
    if original_name:
        response['Content-Disposition'] = f'inline; filename="{original_name}"'
    return response

# Touch reloader trigger

