from django.db import models
from django.conf import settings
import uuid


# Create your models here.
class Payment(models.Model):
    PENDING = 'pending'
    SUCCESSFUL = 'successful'
    FAILED = 'failed'
    REFUNDED = 'refunded'
    
    STATUS_CHOICES = (
        (PENDING, 'Pending'),
        (SUCCESSFUL, 'Successful'),
        (FAILED, 'failed'),
        (REFUNDED, 'Refunded'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    order_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    cuurency = models.CharField(max_length=3, default='IRR')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    card_number = models.CharField(max_length=16, blank=True, null=True)
    ref_id = models.CharField(max_length=100, blank=True, null=True)
    tracking_code = models.CharField(max_length=100, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    
    #Gateway info
    gateway = models.CharField(max_length=255, default='ZarinPal')
    gateway_response = models.JSONField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def mark_successful(self, ref_id, tracking_code, response_data=None):
        self.status = self.SUCCESSFUL
        self.ref_id = ref_id
        self.tracking_code = tracking_code
        if response_data:
            self.gateway_response = response_data
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
        
    def __str__(self):
        return f"Payment {self.order_id} - {self.user} - {self.status}"