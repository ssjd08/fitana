from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from datetime import timedelta
import uuid


class UserManager(BaseUserManager):
    def create_user(self, phone, first_name='', last_name='', email='', password=None, **extra_fields):
        if not phone:
            raise ValueError("The phone number is required")
        user = self.model(phone=phone, first_name=first_name, last_name=last_name, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if password is None:
            raise ValueError("Superusers must have a password")
        return self.create_user(phone, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    MEMBERSHIP_BRONZE = 'B'
    MEMBERSHIP_SILVER = 'S'
    MEMBERSHIP_GOLD = 'G'

    MEMBERSHIP_CHOICES = [
        (MEMBERSHIP_BRONZE, 'Bronze'),
        (MEMBERSHIP_SILVER, 'Silver'),
        (MEMBERSHIP_GOLD, 'Gold'),
    ]
    
    # Add username field for JWT compatibility
    username = models.CharField(max_length=150, unique=True, blank=True)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, unique=True)  # Reduced from 255
    phone_verified = models.BooleanField(default=False)
    birth_date = models.DateField(null=True, blank=True)
    membership = models.CharField(
        max_length=1, choices=MEMBERSHIP_CHOICES, default=MEMBERSHIP_BRONZE)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        # Auto-generate username from phone if not provided
        if not self.username:
            self.username = self.phone
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.first_name} {self.last_name}' if self.first_name or self.last_name else self.phone


    @property
    def is_phone_verified(self):
        return self.phone_verified_at is not None
    
    class Meta:
        ordering = ['first_name', 'last_name']
        
        
class PhoneOTP(models.Model):
    """Stores OTP codes for phone verification"""
    phone = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)  # Prevent OTP reuse

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)  # Reduced from 10
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return not self.is_expired() and not self.is_used

    def __str__(self):
        return f"OTP for {self.phone}"
    
    @classmethod
    def cleanup_expired(cls):
        """Remove expired OTP records and return count of deleted records"""
        expired_otps = cls.objects.filter(expires_at__lt=timezone.now())
        count, _ = expired_otps.delete()
        return count
    
    class Meta:
        ordering = ['-created_at']
        
        
class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)