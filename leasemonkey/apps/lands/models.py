from django.db import models
from django.conf import settings

class Land(models.Model):
    name = models.CharField(max_length=150)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lands'
    )
    area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Area in Acres"
    )
    average_plot_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Average Plot Price"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.username})"
