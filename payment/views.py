from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Payment
from .serializers import PaymentCreateSerializer, PaymentDetailSerializer
from .gateway import MockGateway


from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction


class PaymentCreateView(generics.CreateAPIView):
    """Create payment and send to gateway."""
    serializer_class = PaymentCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create payment and process through gateway."""
        # Save payment with pending status
        payment = serializer.save(user=self.request.user, status=Payment.PENDING)
        
        try:
            # Send to mock gateway
            gateway_data = MockGateway.create_payment(
                amount=payment.amount,
                card_number=serializer.validated_data.get("card_number"),
                description=payment.description,
            )
            
            # Update payment with gateway response
            payment.gateway_response = gateway_data
            payment.ref_id = gateway_data["ref_id"]
            payment.tracking_code = gateway_data["tracking_code"]
            payment.save()
            
        except Exception as e:
            # Update payment status to failed if gateway error occurs
            payment.status = Payment.FAILED
            payment.save()
            raise e
        
        return payment

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create payment with atomic transaction."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        payment = self.perform_create(serializer)
        
        detail_serializer = PaymentDetailSerializer(payment)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
    

class PaymentVerifyView(generics.RetrieveAPIView):
    """Verify a payment using the ref_id."""
    serializer_class = PaymentDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "ref_id"
    queryset = Payment.objects.all()

    def retrieve(self, request, *args, **kwargs):
        payment = self.get_object()
        if payment.status == Payment.SUCCESSFUL:
            return Response(self.get_serializer(payment).data)

        result = MockGateway.verify_payment(payment.ref_id)
        if result["status"] == "success":
            payment.mark_successful(
                ref_id=payment.ref_id,
                tracking_code=payment.tracking_code,
                response_data=result,
            )
        else:
            payment.mark_failed(response_data=result)

        return Response(self.get_serializer(payment).data)
