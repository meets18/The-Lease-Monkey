from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

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


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_preferences(sender, instance, created, **kwargs):
    if created:
        UserPreferences.objects.get_or_create(user=instance)

