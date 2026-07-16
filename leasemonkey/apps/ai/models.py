from django.db import models
from django.conf import settings

# Backward-compatible alias for old migration references
from apps.core.models import _ticket_attachment_path as ticket_attachment_path

class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session {self.id} - {self.user.username if self.user else 'Guest'}"

class ChatMessage(models.Model):
    SENDER_CHOICES = [
        ('USER', 'User'),
        ('AI', 'Assistant'),
    ]
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message_text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.message_text[:30]}"

class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RESOLVED', 'Resolved'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='support_tickets')
    chat_session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    user_query = models.TextField()
    admin_notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Ticket #{self.id} ({self.status}) - {self.user.username if self.user else 'Guest'}"



