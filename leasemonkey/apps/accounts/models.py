import re
import random
import secrets
import string
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        email = self.normalize_email(email) if email else None
        extra_fields.setdefault('is_active', True)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('status', 'ACTIVE')
        extra_fields.setdefault('is_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)

class User(AbstractUser):
    username = models.CharField(max_length=150, primary_key=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    
    BUYER = 'BUYER'
    LAND_OWNER = 'LAND_OWNER'
    ADMIN = 'ADMIN'
    
    ROLE_CHOICES = [
        (BUYER, 'Buyer'),
        (LAND_OWNER, 'Land Owner'),
        (ADMIN, 'Admin'),
    ]
    
    PENDING = 'PENDING'
    ACTIVE = 'ACTIVE'
    SUSPENDED = 'SUSPENDED'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (ACTIVE, 'Active'),
        (SUSPENDED, 'Suspended'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=BUYER)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    is_verified = models.BooleanField(default=False)
    is_first_login = models.BooleanField(default=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.username


CONDITION_CHOICES = [
    ('never_leased', 'Never Leased'),
    ('previously_leased', 'Previously Leased'),
    ('no_preference', 'No Preference'),
]

PROXIMITY_CHOICES = [
    ('school', 'School'),
    ('highway', 'Highway'),
    ('hospital', 'Hospital'),
    ('railway', 'Railway Station'),
    ('airport', 'Airport'),
    ('city_center', 'City Center'),
    ('water_source', 'Water Source'),
]

class UserPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    min_budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    max_budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    min_acres = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_acres = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    property_condition = models.CharField(max_length=50, choices=CONDITION_CHOICES, default='no_preference')
    proximity_preferences = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"


class LandownerApplication(models.Model):
    APPLICATION_STATUS = [
        ('PENDING', 'Pending'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    # Personal Information (Step 1)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    mobile_number = models.CharField(max_length=15)
    email = models.EmailField()

    # Government Information (Step 2)
    aadhaar_number = models.CharField(max_length=12)
    pan_number = models.CharField(max_length=10)

    # Land Information (Step 3)
    land_name = models.CharField(max_length=200)
    land_address = models.TextField()
    state = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6)
    total_area = models.DecimalField(max_digits=10, decimal_places=2)
    ownership_details = models.TextField()

    # Document Upload (Step 4)
    aadhaar_document = models.FileField(upload_to='landowner_applications/documents/')
    pan_document = models.FileField(upload_to='landowner_applications/documents/')
    ownership_document = models.FileField(upload_to='landowner_applications/documents/')

    # Verification
    email_verified = models.BooleanField(default=False)

    # Status
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='PENDING')
    rejection_reason = models.TextField(blank=True)
    admin_remarks = models.TextField(blank=True)
    approved_user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='landowner_application')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_status_display()}"

    @staticmethod
    def generate_username(first_name, last_name):
        base = re.sub(r'[^a-zA-Z0-9]', '', f"{first_name}{last_name}".lower())
        if not base:
            base = 'user'
        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        return username

    @staticmethod
    def generate_password(length=16):
        alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def approve(self, admin_user):
        username = self.generate_username(self.first_name, self.last_name)
        password = self.generate_password()
        user = User.objects.create_user(
            username=username,
            email=self.email,
            password=password,
            role=User.LAND_OWNER,
            status=User.ACTIVE,
            is_verified=True,
            phone_number=self.mobile_number,
            date_of_birth=self.date_of_birth,
            first_name=self.first_name,
            last_name=self.last_name,
        )
        self.approved_user = user
        self.status = 'APPROVED'
        self.reviewed_at = timezone.now()
        self.save(update_fields=['approved_user', 'status', 'reviewed_at', 'updated_at'])
        return user, password

    def reject(self, admin_user, reason=''):
        self.status = 'REJECTED'
        self.rejection_reason = reason
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'rejection_reason', 'reviewed_at', 'updated_at'])


class OCRValidation(models.Model):
    VALIDATION_STATUS = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('completed',  'Completed'),
        ('failed',     'OCR Processing Failed'),
    ]
    RISK_LEVEL_CHOICES = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
        ('failed', 'Failed'),
    ]

    application = models.OneToOneField(
        LandownerApplication,
        on_delete=models.CASCADE,
        related_name='ocr_validation'
    )

    # Aadhaar card results
    aadhaar_doc_type_detected = models.BooleanField(null=True, blank=True)
    aadhaar_number_found      = models.BooleanField(null=True, blank=True)
    aadhaar_number_match      = models.BooleanField(null=True, blank=True)
    aadhaar_ocr_number        = models.CharField(max_length=20, blank=True)
    aadhaar_confidence        = models.FloatField(null=True, blank=True)

    # PAN card results
    pan_doc_type_detected     = models.BooleanField(null=True, blank=True)
    pan_number_found          = models.BooleanField(null=True, blank=True)
    pan_number_match          = models.BooleanField(null=True, blank=True)
    pan_ocr_number            = models.CharField(max_length=15, blank=True)
    pan_confidence            = models.FloatField(null=True, blank=True)

    # Optional cross-checks
    name_match_score          = models.FloatField(null=True, blank=True)
    dob_match                 = models.BooleanField(null=True, blank=True)

    # Risk assessment
    risk_score                = models.IntegerField(default=0)
    risk_level                = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, blank=True)
    validation_flags          = models.JSONField(default=list, blank=True)

    # Raw OCR text for debugging (admin-only access)
    aadhaar_raw_text          = models.TextField(blank=True)
    pan_raw_text              = models.TextField(blank=True)

    # Pipeline state
    validation_status         = models.CharField(max_length=20, choices=VALIDATION_STATUS, default='pending')
    error_message             = models.TextField(blank=True)
    processed_at              = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-processed_at']

    def __str__(self):
        return f"OCR [{self.risk_level or 'pending'}] — App #{self.application_id}"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_preferences(sender, instance, created, **kwargs):
    if created:
        UserPreferences.objects.get_or_create(user=instance)

