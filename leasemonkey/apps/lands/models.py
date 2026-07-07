from django.db import models
from django.conf import settings
from django.utils.text import slugify

class Land(models.Model):
    name = models.CharField(max_length=150, unique=True)
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
    description = models.TextField(
        blank=True,
        help_text="Detailed information about the land, amenities, and surroundings"
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


class Building(models.Model):
    land = models.ForeignKey(
        Land,
        on_delete=models.CASCADE,
        related_name='buildings'
    )
    building_id = models.CharField(
        max_length=50,
        help_text="Unique building identifier, e.g. Block-A, T-Court"
    )
    area = models.CharField(max_length=50, help_text="e.g. 0.3450 acres")
    height = models.IntegerField(default=1, help_text="Number of floors for 3D extrusion")
    coordinates = models.JSONField(help_text="List of [lat, lng] pairs defining the building footprint")
    center_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    center_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['building_id']
        unique_together = ('land', 'building_id')

    def __str__(self):
        return f"Building {self.building_id} - {self.land.name}"

def get_land_gallery_upload_path(instance, filename):
    """Saves gallery photographs into a subfolder named after the land's slug."""
    return f"land_gallery/{instance.land.slug}/{filename}"

class LandImage(models.Model):
    land = models.ForeignKey(Land, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=get_land_gallery_upload_path)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.land.name}"

class Road(models.Model):
    land = models.ForeignKey(Land, on_delete=models.CASCADE, related_name='roads')
    name = models.CharField(max_length=150)
    coordinates = models.JSONField(help_text="JSON list of [lat, lng] coordinates defining the road path")
    width_meters = models.DecimalField(max_digits=5, decimal_places=1, default=9.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Road {self.name} - {self.land.name}"

class EntryExitPoint(models.Model):
    POINT_TYPES = [
        ('entry', 'Entry Point'),
        ('exit', 'Exit Point'),
        ('both', 'Entry & Exit Point'),
    ]
    land = models.ForeignKey(Land, on_delete=models.CASCADE, related_name='points')
    name = models.CharField(max_length=100)
    point_type = models.CharField(max_length=20, choices=POINT_TYPES, default='entry')
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_point_type_display()}: {self.name} - {self.land.name}"

# Signal handlers to clean up physical storage files on model instance deletions
from django.db.models.signals import post_delete
from django.dispatch import receiver
import os
import shutil

@receiver(post_delete, sender=LandImage)
def delete_land_image_file(sender, instance, **kwargs):
    """Deletes the physical image file from disk storage when a LandImage is deleted."""
    if instance.image:
        try:
            if os.path.isfile(instance.image.path):
                os.remove(instance.image.path)
        except Exception:
            pass

@receiver(post_delete, sender=Land)
def delete_land_media_directory(sender, instance, **kwargs):
    """Deletes the entire land-specific subfolder in media/ when a Land is deleted."""
    try:
        from django.conf import settings
        land_dir = os.path.join(settings.MEDIA_ROOT, 'land_gallery', instance.slug)
        if os.path.isdir(land_dir):
            shutil.rmtree(land_dir)
    except Exception:
        pass
