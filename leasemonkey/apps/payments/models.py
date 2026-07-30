from django.db import models
from django.conf import settings
from django.utils import timezone
import datetime

class LandSubscription(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('pending', 'Pending Payment'),
        ('cancelled', 'Cancelled'),
    )

    land = models.ForeignKey('lands.Land', on_delete=models.CASCADE, related_name='subscriptions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='land_subscriptions')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=200.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.land.name} - {self.user.username} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.end_date and self.start_date:
            self.end_date = self.start_date + datetime.timedelta(days=30)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        if self.status == 'active' and self.end_date:
            return self.end_date >= timezone.now()
        return False


class PaymentTransaction(models.Model):
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
    )

    subscription = models.ForeignKey(LandSubscription, on_delete=models.CASCADE, related_name='transactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_transactions')
    transaction_id = models.CharField(max_length=100, unique=True)
    order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    payment_session_id = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Cashfree Sandbox')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_id} - ₹{self.amount} ({self.status})"
