from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


# Create your models here.
class Payment(models.Model):
    PENDING = 'pending'
    SUCCESSFUL = 'successful'
    FAILED = 'failed'
    REFUNDED = 'refunded'
    CANCELLED = 'cancelled'
    
    STATUS_CHOICES = (
        (PENDING, 'Pending'),
        (SUCCESSFUL, 'Successful'),
        (FAILED, 'failed'),
        (REFUNDED, 'Refunded'),
        (CANCELLED, 'Cancelled'),
    )
    
    CURRENCY_CHOICES = (
        ('IRR', 'Iranian Rial'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    order_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=0, validators=[MinValueValidator(1000)])
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='IRR')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    
    # Card info (masked for security)
    card_number_masked = models.CharField(max_length=19, blank=True, null=True)
    
    # Gateway response data
    ref_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    tracking_code = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    #Gateway info
    gateway = models.CharField(max_length=255, default='ZarinPal')
    gateway_response = models.JSONField(blank=True, null=True)
    gateway_authority = models.CharField(max_length=100, blank=True, null=True)  # For ZarinPal
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['ref_id']),
        ]
        
    def __str__(self):
        return f"Payment {self.order_id} - {self.user} - {self.status}"
    
    @staticmethod
    def mask_card_number(card_number):
        """Mask card number for security: 1234567812345678 -> **** **** **** 5678"""
        if not card_number or len(card_number) < 4:
            return card_number
        return "**** **** **** " + card_number[-4:]
    
    def mark_successful(self, ref_id=None, tracking_code=None, response_data=None):
        """Update payment status to successful."""
        from django.utils import timezone
        
        self.status = self.SUCCESSFUL
        if ref_id:
            self.ref_id = ref_id
        if tracking_code:
            self.tracking_code = tracking_code
        if response_data:
            self.gateway_response = response_data
        self.verified_at = timezone.now()
        self.save()
        
    def mark_failed(self, response_data=None):
        """Update status when payment fails."""
        self.status = self.FAILED
        if response_data:
            self.gateway_response = response_data
        self.save()

    def mark_refunded(self, response_data=None):
        """Mark payment as refunded."""
        self.status = self.REFUNDED
        if response_data:
            self.gateway_response = response_data
        self.save()
    
    def mark_cancelled(self, response_data=None):
        """Mark payment as cancelled."""
        self.status = self.CANCELLED
        if response_data:
            self.gateway_response = response_data
        self.save()
    
    @property
    def is_successful(self):
        return self.status == self.SUCCESSFUL
    
    @property
    def is_pending(self):
        return self.status == self.PENDING
    
    @property
    def can_be_refunded(self):
        return self.status == self.SUCCESSFUL
    
    def get_amount_display(self):
        """Return formatted amount with currency."""
        if self.currency == 'IRR':
            return f"{self.amount:,} ریال"
        return f"{self.amount} {self.currency}"