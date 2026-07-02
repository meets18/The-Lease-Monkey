from django.db import models
from django.conf import settings
from django.utils.text import slugify

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
    location = models.CharField(
        max_length=255,
        default='Sitapura, Jaipur'
    )
    slug = models.SlugField(
        max_length=150,
        unique=True,
        null=True,
        blank=True
    )
    boundary_coordinates = models.JSONField(
        default=list,
        blank=True,
        help_text="List of [lat, lng] pairs defining the boundary"
    )
    center_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    center_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    zoom_level = models.IntegerField(
        default=17
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            base_slug = self.slug
            counter = 1
            while Land.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.username})"

class Plot(models.Model):
    FACING_CHOICES = [
        ('North', 'North'),
        ('South', 'South'),
        ('East', 'East'),
        ('West', 'West'),
        ('North-East', 'North-East'),
        ('North-West', 'North-West'),
        ('South-East', 'South-East'),
        ('South-West', 'South-West'),
    ]
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
    ]

    land = models.ForeignKey(
        Land,
        on_delete=models.CASCADE,
        related_name='plots'
    )
    plot_number = models.CharField(max_length=50)
    area = models.CharField(max_length=50, help_text="e.g. 1,500 sqft")
    price = models.DecimalField(max_digits=12, decimal_places=2)
    facing = models.CharField(max_length=50, choices=FACING_CHOICES, default='North')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    coordinates = models.JSONField(help_text="List of [lat, lng] pairs defining the plot outline")
    center_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    center_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['plot_number']
        unique_together = ('land', 'plot_number')

    def __str__(self):
        return f"Plot {self.plot_number} - {self.land.name}"
