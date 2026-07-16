from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone

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
    is_live = models.BooleanField(
        default=False,
        help_text="If True, this property is visible to buyers in the directory."
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

class SavedPlot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_plots')
    land = models.ForeignKey(Land, on_delete=models.CASCADE, related_name='saved_by_users')
    plot_number = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'land', 'plot_number')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} saved {self.plot_number} in {self.land.name}"


class OccupancyRecord(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('terminated', 'Terminated'),
    ]
    land = models.ForeignKey(Land, on_delete=models.CASCADE, related_name='occupancy_records')
    plot_number = models.CharField(max_length=50)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='occupancy_records')
    allotted_at = models.DateTimeField(default=timezone.now)
    deallotted_at = models.DateTimeField(null=True, blank=True)
    deallotment_reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    class Meta:
        ordering = ['-allotted_at']

    def __str__(self):
        return f"{self.plot_number} - {self.buyer.username} ({self.status})"

def get_ownership_proof_path(instance, filename):
    return f"land_requests/{instance.owner.username}/ownership_{filename}"

def get_registry_sale_deed_path(instance, filename):
    return f"land_requests/{instance.owner.username}/registry_{filename}"

def get_supporting_docs_path(instance, filename):
    return f"land_requests/{instance.owner.username}/supporting_{filename}"

def get_floor_plan_path(instance, filename):
    return f"land_requests/{instance.owner.username}/floor_plan_{filename}"

class LandRegistrationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('being_added', 'Being Added'),
        ('approved', 'Approved'),
        ('live', 'Live'),
        ('rejected', 'Rejected'),
        ('deleted', 'Deleted'),
    ]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='land_reg_requests')
    property_name = models.CharField(max_length=200)
    
    # Precise Location Fields
    state = models.CharField(max_length=100, default='')
    district = models.CharField(max_length=100, default='')
    city_village = models.CharField(max_length=150, default='')
    complete_address = models.TextField(default='')
    pin_code = models.CharField(max_length=10, default='')
    
    location = models.CharField(max_length=300) # Kept for compatibility
    google_maps_link = models.URLField(blank=True, null=True, help_text="Optional Google Maps link")
    description = models.TextField(blank=True)
    average_plot_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Document Files
    ownership_proof = models.FileField(upload_to=get_ownership_proof_path, help_text="Registry document, sale deed, or other ownership proof (PDF/image)")
    registry_sale_deed = models.FileField(upload_to=get_registry_sale_deed_path, blank=True, null=True, help_text="Registry / Sale Deed document")
    supporting_documents = models.FileField(upload_to=get_supporting_docs_path, blank=True, null=True, help_text="Additional supporting documents")
    floor_plan = models.FileField(upload_to=get_floor_plan_path, help_text="Site layout / floor plan showing plot arrangement (PDF/image)")
    
    notes = models.TextField(blank=True, help_text="Landowner's notes to admin")
    admin_remarks = models.TextField(blank=True, help_text="Internal admin notes (not shown to landowner)")
    rejection_reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    land = models.OneToOneField(Land, on_delete=models.SET_NULL, null=True, blank=True, related_name='registration_request')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Request: {self.property_name} by {self.owner.username} ({self.status})"

# Signal handlers to clean up physical storage files on model instance deletions
from django.db.models.signals import post_delete, pre_delete
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

@receiver(pre_delete, sender=Land)
def mark_land_registration_request_deleted(sender, instance, **kwargs):
    """When a Land is deleted, mark its registration request as 'deleted'."""
    try:
        req = LandRegistrationRequest.objects.filter(land=instance).first()
        if req and req.status not in ('rejected', 'deleted'):
            req.status = 'deleted'
            req.save(update_fields=['status'])
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
