import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.generic import TemplateView
from .models import Notification


def _get_notification_item_label(notif):
    """Build a user-facing notification target label without exposing slugs."""
    from apps.lands.models import Land

    land_name = None
    if notif.land_slug:
        try:
            land_name = Land.objects.only('name').get(slug=notif.land_slug).name
        except Land.DoesNotExist:
            pass

    if notif.notif_type == 'land_delete_request':
        return f"Land {land_name}" if land_name else "the selected land"

    if notif.notif_type == 'plot_delete_request':
        kind = "Building" if notif.plot_kind == 'building' else "Plot"
        if land_name:
            return f"{kind} {notif.plot_number} in {land_name}"
        return f"{kind} {notif.plot_number}"

    return "your deletion request"


class LandingPageView(TemplateView):
    template_name = "landing.html"


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
        if notif.notif_type == 'land_delete_request':
            land = Land.objects.get(slug=notif.land_slug)
            land_name = land.name
            item_label = f"Land: {land_name}"
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
            if obj:
                obj.delete()
            else:
                return JsonResponse({'error': 'Item not found. It may have already been deleted.'}, status=404)
        else:
            return JsonResponse({'error': 'Cannot approve this notification type.'}, status=400)

    except Land.DoesNotExist:
        return JsonResponse({'error': 'Land not found. It may have already been deleted.'}, status=404)

    # Mark original notification as resolved
    notif.is_read = True
    notif.is_resolved = True
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
    item_label = _get_notification_item_label(notif)

    # Mark original notification as resolved
    notif.is_read = True
    notif.is_resolved = True
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
    """Deletes a notification only from the current user's notification tab."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=400)
    try:
        notif = Notification.objects.get(id=notification_id, recipient=request.user)
        notif.delete()
        return JsonResponse({'status': 'deleted'})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Not found.'}, status=404)
