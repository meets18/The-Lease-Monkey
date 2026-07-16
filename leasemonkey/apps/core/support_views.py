import json
import logging
from django.utils import timezone
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _get_admin_emails():
    from apps.accounts.models import User
    admins = User.objects.filter(role=User.ADMIN)
    if not admins.exists():
        admins = User.objects.filter(is_superuser=True)
    return list(admins.values_list('email', flat=True)) or [settings.ADMIN_EMAIL] if settings.ADMIN_EMAIL else []


def _get_next_ticket_id():
    year = timezone.now().year
    from .models import Ticket
    last_ticket = Ticket.objects.filter(ticket_id__startswith=f'LM-{year}').order_by('-ticket_id').first()
    if last_ticket:
        last_num = int(last_ticket.ticket_id.split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f'LM-{year}-{new_num:04d}'


def _send_ticket_created_emails(ticket):
    admin_emails = _get_admin_emails()
    attachment_path = ticket.attachment.path if ticket.attachment else None

    try:
        admin_msg = (
            f"Hello Admin,\n\n"
            f"A new support ticket has been created.\n\n"
            f"Ticket ID: {ticket.ticket_id}\n"
            f"User: {ticket.user.username}\n"
            f"Role: {ticket.role}\n"
            f"Email: {ticket.user.email}\n"
            f"Subject: {ticket.subject}\n"
            f"Category: {ticket.get_category_display()}\n"
            f"Description:\n{ticket.description}\n\n"
            f"Please review and respond at your earliest convenience.\n\n"
            f"— The Lease Monkey Support System"
        )
        email = EmailMessage(
            subject=f'[Lease Monkey] New Support Ticket — {ticket.ticket_id}',
            body=admin_msg,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=admin_emails,
        )
        if attachment_path:
            email.attach_file(attachment_path)
        email.send(fail_silently=True)
    except Exception as e:
        logger.error(f"Failed to send admin email for ticket {ticket.ticket_id}: {e}")

    try:
        user_msg = (
            f"Hello {ticket.user.username},\n\n"
            f"Your support request has been received successfully.\n\n"
            f"Ticket ID: {ticket.ticket_id}\n"
            f"Subject: {ticket.subject}\n"
            f"Category: {ticket.get_category_display()}\n\n"
            f"Our support team will respond shortly.\n\n"
            f"You can monitor the ticket from your dashboard.\n\n"
            f"Thank you,\n"
            f"Lease Monkey Support"
        )
        send_mail(
            subject='Support Ticket Received',
            message=user_msg,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ticket.user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"Failed to send confirmation email for ticket {ticket.ticket_id}: {e}")


def _send_ticket_reply_emails(ticket, reply, is_admin_reply=True):
    if is_admin_reply:
        recipient_list = [ticket.user.email]
        subject = f'Update on your Lease Monkey Support Ticket ({ticket.ticket_id})'
        body = (
            f"Hello {ticket.user.username},\n\n"
            f"Our support team has replied to your support request.\n\n"
            f"Ticket ID\n\n"
            f"{ticket.ticket_id}\n\n"
            f"Reply\n"
            f"{'─' * 40}\n"
            f"{reply.message}\n"
            f"{'─' * 40}\n\n"
            f"You can continue the conversation from:\n\n"
            f"Dashboard\n"
            f"  → Help & Support\n"
            f"  → My Tickets\n\n"
            f"Thank you,\n"
            f"Lease Monkey Support"
        )
    else:
        admin_emails = _get_admin_emails()
        recipient_list = admin_emails
        subject = f'[Lease Monkey] User replied to ticket — {ticket.ticket_id}'
        body = (
            f"Hello Admin,\n\n"
            f"{ticket.user.username} has replied to support ticket {ticket.ticket_id}.\n\n"
            f"Subject: {ticket.subject}\n"
            f"Message:\n{reply.message}\n\n"
            f"Please log in to the admin dashboard to respond.\n\n"
            f"— The Lease Monkey Support System"
        )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"Failed to send reply email for ticket {ticket.ticket_id}: {e}")


@login_required
def help_support(request):
    if request.user.role not in ('BUYER', 'LAND_OWNER'):
        raise PermissionDenied("Only buyers and landowners can access this page.")

    # Both roles now have Help & Support as a tab in their dashboard.
    from django.shortcuts import redirect
    if request.user.role == 'BUYER':
        return redirect('buyer_dashboard')
    if request.user.role == 'LAND_OWNER':
        return redirect('landowner_dashboard')

    from .models import Ticket
    tickets = Ticket.objects.filter(user=request.user).order_by('-created_at')

    faqs = [
        {
            'question': 'How long does verification take?',
            'answer': 'Verification typically takes 2-3 business days after submitting all required documents. You will be notified via email once the verification is complete.',
        },
        {
            'question': 'How are plots approved?',
            'answer': 'Plots are approved after the landowner and buyer complete a scheduled meeting. The landowner can then approve the purchase request from their dashboard.',
        },
        {
            'question': 'How do meetings work?',
            'answer': 'Meetings are scheduled through the platform. Once a purchase request is submitted, the landowner can schedule a meeting with the buyer. Both parties receive the meeting link and reminders.',
        },
        {
            'question': 'How do I update my profile?',
            'answer': 'You can update your profile by clicking on "Profile" in the sidebar navigation. From there, you can edit your personal information, contact details, and preferences.',
        },
        {
            'question': 'Can I cancel a purchase request?',
            'answer': 'Yes, you can cancel a purchase request while it is still in "Pending" status. Contact support if you need assistance with an already-processed request.',
        },
    ]

    context = {
        'tickets': tickets,
        'faqs': faqs,
    }
    return render(request, 'core/help_support.html', context)


@login_required
def ticket_conversation(request, ticket_id):
    from .models import Ticket
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    if ticket.user != request.user and request.user.role != 'ADMIN':
        raise PermissionDenied("You do not have access to this ticket.")

    replies = ticket.replies.all()

    context = {
        'ticket': ticket,
        'replies': replies,
    }
    return render(request, 'core/ticket_conversation.html', context)


@login_required
@require_POST
def create_ticket_ajax(request):
    if request.user.role not in ('BUYER', 'LAND_OWNER'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    from .models import Ticket
    subject = request.POST.get('subject', '').strip()
    category = request.POST.get('category', '')
    description = request.POST.get('description', '').strip()

    if not subject or not description:
        return JsonResponse({'error': 'Subject and description are required.'}, status=400)

    if category not in dict(Ticket.CATEGORY_CHOICES):
        return JsonResponse({'error': 'Invalid category.'}, status=400)

    ticket_id = _get_next_ticket_id()
    attachment = request.FILES.get('attachment') if request.FILES else None

    if attachment:
        valid_extensions = ('.pdf', '.png', '.jpg', '.jpeg')
        if not any(attachment.name.lower().endswith(ext) for ext in valid_extensions):
            return JsonResponse({'error': 'Invalid file type. Allowed: PDF, PNG, JPG, JPEG.'}, status=400)
        if attachment.size > 10 * 1024 * 1024:
            return JsonResponse({'error': 'File too large. Maximum size is 10 MB.'}, status=400)

    ticket = Ticket.objects.create(
        ticket_id=ticket_id,
        user=request.user,
        role=request.user.role,
        subject=subject,
        category=category,
        description=description,
        attachment=attachment,
    )

    # Create notification for admins
    admin_emails = _get_admin_emails()
    for admin_email in admin_emails:
        try:
            from apps.accounts.models import User
            admin_user = User.objects.get(email=admin_email)
            from .models import Notification
            Notification.objects.create(
                recipient=admin_user,
                sender=request.user,
                notif_type='support_ticket_created',
                title=f'New Support Ticket: {ticket.ticket_id}',
                message=f'{request.user.username} ({request.user.role}) created a support ticket: {ticket.subject}',
                ticket_id=ticket.ticket_id,
            )
        except User.DoesNotExist:
            pass

    # Send emails
    _send_ticket_created_emails(ticket)

    return JsonResponse({
        'status': 'ok',
        'ticket_id': ticket.ticket_id,
        'message': 'Support ticket created successfully.',
    })


@login_required
@require_POST
def reply_ticket_ajax(request, ticket_id):
    from .models import Ticket, TicketReply
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)

    if ticket.user != request.user and request.user.role != 'ADMIN':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if ticket.status == 'closed':
        return JsonResponse({'error': 'Cannot reply to a closed ticket.'}, status=400)

    message = request.POST.get('message', '').strip()
    if not message:
        return JsonResponse({'error': 'Message is required.'}, status=400)

    attachment = request.FILES.get('attachment') if request.FILES else None
    if attachment:
        valid_extensions = ('.pdf', '.png', '.jpg', '.jpeg')
        if not any(attachment.name.lower().endswith(ext) for ext in valid_extensions):
            return JsonResponse({'error': 'Invalid file type. Allowed: PDF, PNG, JPG, JPEG.'}, status=400)
        if attachment.size > 10 * 1024 * 1024:
            return JsonResponse({'error': 'File too large. Maximum size is 10 MB.'}, status=400)

    reply = TicketReply.objects.create(
        ticket=ticket,
        sender=request.user,
        message=message,
        attachment=attachment,
    )

    is_admin_reply = request.user.role == 'ADMIN'

    # Create notification
    if is_admin_reply:
        from .models import Notification
        Notification.objects.create(
            recipient=ticket.user,
            sender=request.user,
            notif_type='support_ticket_replied',
            title=f'Support replied to your ticket {ticket.ticket_id}',
            message=f'Tap to view.',
            ticket_id=ticket.ticket_id,
        )
    else:
        admin_emails = _get_admin_emails()
        for admin_email in admin_emails:
            try:
                from apps.accounts.models import User
                admin_user = User.objects.get(email=admin_email)
                from .models import Notification
                Notification.objects.create(
                    recipient=admin_user,
                    sender=request.user,
                    notif_type='support_ticket_replied',
                    title=f'User replied to {ticket.ticket_id}',
                    message=f'{request.user.username} replied to ticket: {ticket.subject}',
                    ticket_id=ticket.ticket_id,
                )
            except User.DoesNotExist:
                pass

    _send_ticket_reply_emails(ticket, reply, is_admin_reply=is_admin_reply)

    return JsonResponse({
        'status': 'ok',
        'message': 'Reply sent successfully.',
    })


@login_required
@require_POST
def update_ticket_status_ajax(request, ticket_id):
    if request.user.role != 'ADMIN':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    from .models import Ticket
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)

    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    new_status = data.get('status', '')
    valid_statuses = [s[0] for s in Ticket.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return JsonResponse({'error': f'Invalid status. Valid: {", ".join(valid_statuses)}'}, status=400)

    old_status = ticket.status
    ticket.status = new_status
    ticket.save()

    from .models import Notification
    Notification.objects.create(
        recipient=ticket.user,
        sender=request.user,
        notif_type='support_ticket_status_changed',
        title=f'Ticket {ticket.ticket_id} status changed',
        message=f'Your ticket "{ticket.subject}" status changed from {dict(Ticket.STATUS_CHOICES)[old_status]} to {dict(Ticket.STATUS_CHOICES)[new_status]}.',
        ticket_id=ticket.ticket_id,
    )

    try:
        send_mail(
            subject=f'[Lease Monkey] Ticket {ticket.ticket_id} status updated',
            message=f'Hello {ticket.user.username},\n\n'
                    f'Your support ticket status has been updated.\n\n'
                    f'Ticket ID: {ticket.ticket_id}\n'
                    f'Subject: {ticket.subject}\n'
                    f'Status: {dict(Ticket.STATUS_CHOICES)[new_status]}\n\n'
                    f'Log in to your dashboard to view the details.\n\n'
                    f'— The Lease Monkey Support',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ticket.user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"Failed to send status email for ticket {ticket.ticket_id}: {e}")

    return JsonResponse({'status': 'ok', 'message': f'Ticket status updated to {dict(Ticket.STATUS_CHOICES)[new_status]}.'})


@login_required
def admin_ticket_detail_ajax(request, ticket_id):
    if request.user.role != 'ADMIN':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    from .models import Ticket
    from django.urls import reverse
    ticket = get_object_or_404(Ticket.objects.select_related('user'), ticket_id=ticket_id)
    replies = ticket.replies.select_related('sender').all()

    replies_data = []
    for r in replies:
        replies_data.append({
            'sender': r.sender.username,
            'sender_role': r.sender.role,
            'message': r.message,
            'attachment': reverse('core:serve_protected_file', kwargs={'model_name': 'ticket_reply', 'pk': r.id}) if r.attachment else None,
            'created_at': r.created_at.strftime('%b %d, %Y %I:%M %p'),
        })

    data = {
        'ticket_id': ticket.ticket_id,
        'user': ticket.user.username,
        'user_email': ticket.user.email,
        'role': ticket.role,
        'subject': ticket.subject,
        'category': ticket.get_category_display(),
        'status': ticket.get_status_display(),
        'description': ticket.description,
        'attachment': reverse('core:serve_protected_file', kwargs={'model_name': 'ticket', 'pk': ticket.id}) if ticket.attachment else None,
        'created_at': ticket.created_at.strftime('%b %d, %Y %I:%M %p'),
        'updated_at': ticket.updated_at.strftime('%b %d, %Y %I:%M %p'),
    }

    return JsonResponse({'ticket': data, 'replies': replies_data})
