from rest_framework import serializers
from .models import User, PhoneOTP
import random

class Userserializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'birth_date', 'membership']
        

class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=11)
    
    def create_otp(self, phone):
        code = str(random.randint(100000, 999999))
        otp = PhoneOTP.objects.create(phone=phone, code=code)
        #TODO:SMS API here
        print(f"DEBUG: Sending OTP {code} to {phone}")
        
    def validate(self, attrs):
        phone = attrs.get("phone")
        # Optionally check phone format here
        return attrs
    
    def create(self, validated_data):
        phone = validated_data['phone']
        self.create_otp(phone)
        return {"phone": phone}
    
class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=11)
    code = serializers.CharField(max_length=6)
    
    def validate(self, attrs):
        phone = attrs.get("phone")
        code = attrs.get("code")
        try:
            otp_obj = PhoneOTP.objects.filter(phone=phone).latest("created_at")
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError("OTP not found")
        
        if otp_obj.is_expired():
            raise serializers.ValidationError("OTP expired")

        if otp_obj.code != code:
            raise serializers.ValidationError("Invalid OTP")

        attrs['otp_obj'] = otp_obj
        return attrs
    
    def create(self, validated_data):
        phone = validated_data['phone']
        opt_obj = validated_data['otp_obj']
        
        user, created = User.objects.get_or_create(phone=phone)
        opt_obj.delete()
        
        return {
            "user" : user,
            "is_new" : created
        }