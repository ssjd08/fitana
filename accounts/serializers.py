import random
import re
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PhoneOTP
from typing import Dict, Any

# Get the User model
User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'phone', 'birth_date', 'membership']
        read_only_fields = ['id', 'phone']  # Phone shouldn't be editable after registration


class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(
        max_length=11,
        min_length=11,
        help_text="Phone number in format 09123456789",
        style={'placeholder': '09123456789'}
    )
    
    def validate_phone(self, value):
        """Validate phone number format"""
        pattern = r"^09\d{9}$"
        if not re.match(pattern, value):
            raise serializers.ValidationError(
                "Phone number must be in format 09XXXXXXXXX (11 digits total)"
            )
        return value
    
    def create_otp(self, phone):
        # Delete any existing OTP for this phone
        PhoneOTP.objects.filter(phone=phone, is_used=False).delete()
        
        # Generate 6-digit OTP
        code = str(random.randint(100000, 999999))
        otp = PhoneOTP.objects.create(phone=phone, code=code)
        
        # TODO: Integrate with SMS provider (Twilio, Kavenegar, etc.)
        print(f"DEBUG: Sending OTP {code} to {phone}")
        return otp
    
    def create(self, validated_data):
        phone = validated_data['phone']
        otp_instance = self.create_otp(phone)
        return {'detail': 'OTP sent successfully', 'session_id': str(otp_instance.session_id)}


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(
        max_length=11,
        help_text="Phone number used to send OTP"
    )
    code = serializers.CharField(
        max_length=6,
        min_length=6,
        help_text="6-digit OTP code received via SMS"
    )
    username = serializers.CharField(
        max_length=150,
        required=False,
        help_text="Desired username for new account (optional - will use phone if not provided)"
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=False,
        help_text="Password for new account (required for new users)"
    )
    email = serializers.EmailField(
        required=False,
        help_text="Email address (optional)"
    )
    first_name = serializers.CharField(
        max_length=255,
        required=False,
        help_text="First name (optional)"
    )
    last_name = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Last name (optional)"
    )
    
    def validate_phone(self, value):
        """Validate phone number format"""
        pattern = r"^09\d{9}$"
        if not re.match(pattern, value):
            raise serializers.ValidationError(
                "Phone number must be in format 09XXXXXXXXX"
            )
        return value
    
    def validate(self, attrs):
        phone = attrs.get('phone')
        code = attrs.get('code')
        username = attrs.get('username')
        password = attrs.get('password')
        
        # Check if OTP exists and is valid
        try:
            otp = PhoneOTP.objects.get(phone=phone, code=code, is_used=False)
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP code or phone number")
        
        # Check if OTP is expired
        if not otp.is_valid():
            otp.delete()  # Clean up expired OTP
            raise serializers.ValidationError("OTP code has expired or already used")
        
        # Check if user already exists
        existing_user = User.objects.filter(phone=phone).first()
        
        if existing_user:
            # User exists - login scenario
            attrs['existing_user'] = existing_user
            attrs['is_new_user'] = False
        else:
            # New user - registration scenario
            attrs['is_new_user'] = True
            
            # Password is required for new users
            if not password:
                raise serializers.ValidationError("Password is required for new account registration")
            
            # Check if username already exists (if provided)
            if username and User.objects.filter(username=username).exists():
                raise serializers.ValidationError("Username already exists")
        
        # Store OTP instance for use in create method
        attrs['otp_instance'] = otp
        return attrs
    
    def create(self, validated_data) -> Dict[str, Any]:
        # Remove OTP instance from validated_data
        otp_instance = validated_data.pop('otp_instance')
        existing_user = validated_data.pop('existing_user', None)
        is_new_user = validated_data.pop('is_new_user')
        
        if existing_user:
            # Mark OTP as used
            otp_instance.is_used = True
            otp_instance.save()
            
            return {'user': existing_user, 'is_new': False}
        else:
            # Create new user
            phone = validated_data.pop('phone')
            code = validated_data.pop('code')  # Remove code from user data
            
            # Use the custom UserManager's create_user method
            user = User.objects.create_user(  # type: ignore
                phone=phone,
                username=validated_data.get('username', phone),  # Use phone as username if not provided
                password=validated_data.get('password'),
                email=validated_data.get('email', ''),
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', '')
            )
            
            # Mark OTP as used
            otp_instance.is_used = True
            otp_instance.save()
            
            return {'user': user, 'is_new': True}