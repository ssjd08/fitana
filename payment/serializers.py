from rest_framework import serializers
from .models import Payment


class PaymentCreateSerializer(serializers.ModelSerializer):
    card_number = serializers.CharField(write_only=True, max_length=16)
    
    class Meta:
        model = Payment
        fields = ('amount', 'cuurency', 'card_number', 'description')
        
        
class PaymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ["id", "user", "order_id", "amount", "cuurency", "status", "card_number", "ref_id", "tracking_code", "description", "gateway", "gateway_response", "created_at", "updated_at",]