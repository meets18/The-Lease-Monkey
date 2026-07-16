import os
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class Notification(models.Model):
    TYPE_CHOICES = [
        ('land_delete_request', 'Land Deletion Request'),
        ('plot_delete_request', 'Plot Deletion Request'),
        ('request_rejected',   'Deletion Request Rejected'),
        ('request_approved',   'Deletion Request Approved'),
        ('purchase_request',          'Purchase Request'),
        ('purchase_request_meeting',  'Meeting Scheduled'),
        ('purchase_request_rejected', 'Purchase Request Rejected'),
        ('purchase_request_approved', 'Purchase Request Approved'),
        ('lo_registration_request',  'Landowner Registration Request'),
        ('lo_registration_approved', 'Landowner Registration Approved'),
        ('lo_registration_rejected', 'Landowner Registration Rejected'),
        ('support_ticket_created',   'Support Ticket Created'),
        ('support_ticket_replied',   'Support Ticket Reply'),
        ('support_ticket_status_changed', 'Support Ticket Status Changed'),
        ('purchase_request_cancelled', 'Purchase Request Cancelled'),
    ]

    ticket_id = models.CharField(max_length=20, null=True, blank=True)

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sent_notifications'
    )
    notif_type  = models.CharField(max_length=50, choices=TYPE_CHOICES, default='land_delete_request')
    title       = models.CharField(max_length=200)
    message     = models.TextField()
    is_read     = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    
    # Context so admin can act on the request
    land_slug   = models.SlugField(null=True, blank=True)
    plot_number = models.CharField(max_length=50, null=True, blank=True)
    plot_kind   = models.CharField(max_length=20, null=True, blank=True,
                                   help_text="'plot' or 'building'")
    landowner_application = models.ForeignKey(
        'accounts.LandownerApplication',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='notifications'
    )

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notif_type}] {self.title} → {self.recipient.username}"

class EmailOTP(models.Model):
    email      = models.EmailField()
    otp_code   = models.CharField(max_length=6)
    is_used    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def is_expired(self):
        return (timezone.now() - self.created_at).total_seconds() > 300  # 5 min

class PurchaseRequest(models.Model):
    STATUS_CHOICES = [
        ('pending',            'Pending'),
        ('meeting_scheduled',  'Meeting Scheduled'),
        ('approved',           'Approved'),
        ('rejected',           'Rejected'),
        ('cancelled',          'Cancelled'),
    ]

    buyer           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='purchase_requests')
    land            = models.ForeignKey('lands.Land', on_delete=models.CASCADE, related_name='purchase_requests')
    plot_number     = models.CharField(max_length=50)
    full_name       = models.CharField(max_length=200)
    aadhaar_number  = models.CharField(max_length=12)
    pan_number      = models.CharField(max_length=10)
    email           = models.EmailField()
    phone_number    = models.CharField(max_length=15)
    proposed_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status          = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    meeting_notes   = models.TextField(blank=True)
    meet_link       = models.URLField(blank=True, null=True)
    meeting_datetime = models.DateTimeField(blank=True, null=True)
    meeting_duration_mins = models.PositiveIntegerField(default=30)
    calendar_event_id = models.CharField(max_length=200, blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_meeting_finished(self):
        if not self.meeting_datetime:
            return True
        from datetime import timedelta
        from django.utils import timezone
        return timezone.now() >= self.meeting_datetime + timedelta(minutes=self.meeting_duration_mins)

    def __str__(self):
        return f"PurchaseRequest by {self.buyer.username} for Plot {self.plot_number} in {self.land.name}"


def _ticket_attachment_path(instance, filename):
    ext = filename.split('.')[-1] if '.' in filename else ''
    name = uuid.uuid4().hex
    return os.path.join('tickets', f'{name}.{ext}')


class Ticket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting', 'Waiting for User'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    CATEGORY_CHOICES = [
        ('general', 'General Question'),
        ('technical', 'Technical Issue'),
        ('property_verification', 'Property Verification'),
        ('meeting', 'Meeting Issue'),
        ('account', 'Account Issue'),
        ('bug', 'Bug Report'),
        ('feature', 'Feature Request'),
        ('other', 'Other'),
    ]

    ticket_id   = models.CharField(max_length=20, unique=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets_new')
    role        = models.CharField(max_length=20)
    subject     = models.CharField(max_length=200)
    category    = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField()
    attachment  = models.FileField(upload_to=_ticket_attachment_path, null=True, blank=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_ticket'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ticket_id} - {self.subject} ({self.get_status_display()})"


class TicketReply(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='replies')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    attachment = models.FileField(upload_to=_ticket_attachment_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_ticketreply'
        ordering = ['created_at']

    def __str__(self):
        return f"Reply by {self.sender.username} on {self.ticket.ticket_id}"
