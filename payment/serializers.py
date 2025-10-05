from rest_framework import serializers
from django.core.validators import RegexValidator
from .models import Payment
import re


class PaymentCreateSerializer(serializers.ModelSerializer):
    card_number = serializers.CharField(
        write_only=True,
        max_length=19,
        min_length=16,
        help_text="16-digit card number",
        validators=[
            RegexValidator(
                regex=r'^[\d\s]+$',
                message="Card number can only contain digits and spaces"
            )
        ]
        )
    
    class Meta:
        model = Payment
        fields = ('amount', 'currency', 'card_number', 'description')
        
    def validate_card_number(self, value):
        """Validate card number format and checksum."""
        # Remove spaces and validate format
        clean_number = re.sub(r'\s', '', value)
        
        if not clean_number.isdigit():
            raise serializers.ValidationError("Card number must contain only digits")
        
        if len(clean_number) != 16:
            raise serializers.ValidationError("Card number must be exactly 16 digits")
        
        # Basic Luhn algorithm check (optional - you can implement this)
        if not self._luhn_check(clean_number): # type: ignore
            raise serializers.ValidationError("Invalid card number")
        
        return clean_number
    
    def validate_amount(self, value):
        """Validate payment amount."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        
        # For IRR, minimum amount validation
        currency = self.initial_data.get('currency', 'IRR') # type: ignore
        if currency == 'IRR' and value < 1000:
            raise serializers.ValidationError("Minimum amount for IRR is 1000")
        
        return value
    
    def _luhn_check(self, card_number):
        """Simple Luhn algorithm implementation for card validation."""
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10 == 0
    
    
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