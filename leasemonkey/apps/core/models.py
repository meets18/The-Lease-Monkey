from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_CHOICES = [
        ('land_delete_request', 'Land Deletion Request'),
        ('plot_delete_request', 'Plot Deletion Request'),
        ('request_rejected',   'Deletion Request Rejected'),
        ('request_approved',   'Deletion Request Approved'),
    ]

    recipient   = models.ForeignKey(
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

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notif_type}] {self.title} → {self.recipient.username}"
