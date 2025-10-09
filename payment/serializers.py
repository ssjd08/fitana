from rest_framework import serializers
from django.core.validators import RegexValidator
from django.utils import timezone
from .models import Payment
import re


class PaymentCreateSerializer(serializers.ModelSerializer):
 
    class Meta:
        model = Payment
        fields = ('amount', 'currency')
        
    
    def validate_amount(self, value):
        """Validate payment amount."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        
        # For IRR, minimum amount validation
        currency = self.initial_data.get('currency', 'IRR') # type: ignore
        if currency == 'IRR' and value < 1000:
            raise serializers.ValidationError("Minimum amount for IRR is 1000")
        
        return value
    
    def validate_currency(self, value):
        """Validate payment currency."""
        if value not in ['IRR', 'USD', 'EUR']:
            raise serializers.ValidationError("Invalid currency")
        return value
    
    def create(self, validated_data):
        """Create payment with auto-generated description."""
        user = self.context['request'].user
        amount = validated_data['amount']
        currency = validated_data.get('currency', 'IRR')
        
        # Auto-generate description
        current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        description = f"User with id {user.id} paying {amount} {currency} on {current_time}"
        
        # Create payment instance
        payment = Payment.objects.create(
            user=user,
            amount=amount,
            currency=currency,
            description=description
        )
        
        return payment
    
    
class PaymentDetailSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    amount_display = serializers.CharField(source='get_amount_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_successful = serializers.BooleanField(read_only=True)
    can_be_refunded = serializers.BooleanField(read_only=True)
    
   
    class Meta:
        model = Payment
        fields = [
            'id',
            'user',
            'order_id',
            'amount',
            'amount_display',
            'currency',
            'status',
            'status_display',
            'card_number_masked',
            'ref_id',
            'tracking_code',
            'description',
            'gateway',
            'gateway_authority',
            'created_at',
            'updated_at',
            'verified_at',
            'is_successful',
            'can_be_refunded'
        ]
        read_only_fields = [
            'id', 'user', 'order_id', 'amount', 'currency', 'status',
            'card_number_masked', 'ref_id', 'tracking_code', 'description',
            'gateway', 'gateway_authority', 'created_at', 'updated_at',
            'verified_at'
        ]
        
class PaymentListSerializer(serializers.ModelSerializer):
    """Simplified serializer for payment lists."""
    amount_display = serializers.CharField(source='get_amount_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'order_id',
            'amount',
            'amount_display',
            'currency',
            'status',
            'status_display',
            'card_number_masked',
            'description',
            'created_at'
        ]
       
        
class PaymentVerifySerializer(serializers.Serializer):
    """Serializer for payment verification requests."""
    ref_id = serializers.CharField(max_length=100)
    
    def validate_ref_id(self, value):
        """Validate that payment exists and belongs to current user."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")
        
        try:
            payment = Payment.objects.get(ref_id=value, user=request.user)
        except Payment.DoesNotExist:
            raise serializers.ValidationError("Payment not found or access denied")
        
        return value