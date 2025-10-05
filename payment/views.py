from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import QuerySet
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Payment
from .serializers import(
    PaymentCreateSerializer,
    PaymentDetailSerializer,
    PaymentListSerializer,
    PaymentVerifySerializer
    )
from .gateway import MockGateway



class PaymentCreateView(generics.CreateAPIView):
    """Create payment and send to gateway."""
    serializer_class = PaymentCreateSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new payment",
        responses={
            201: PaymentDetailSerializer,
            400: "Validation errors",
            401: "Authentication required"
        }
    )
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create payment with atomic transaction."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create payment with pending status
        payment = Payment.objects.create(
            user=request.user,
            amount=serializer.validated_data['amount'],
            currency=serializer.validated_data['currency'],
            description=serializer.validated_data.get('description', ''),
            status=Payment.PENDING
        )
        
        # Mask and store card number
        card_number = serializer.validated_data['card_number']
        payment.card_number_masked = Payment.mask_card_number(card_number)
        
        try:
            # Send to gateway
            gateway_response = MockGateway.create_payment(
                amount=payment.amount,
                card_number=card_number,
                description=payment.description or ''
            )
            
            # Update payment with gateway response
            payment.gateway_response = gateway_response
            
            if gateway_response.get('status') == 'success':
                payment.ref_id = gateway_response.get('ref_id')
                payment.tracking_code = gateway_response.get('tracking_code')
                payment.gateway_authority = gateway_response.get('authority')
            else:
                # Gateway returned error
                payment.mark_failed(response_data=gateway_response)
            
            payment.save()
            
        except Exception as e:
            # Gateway communication failed
            payment.mark_failed(response_data={'error': str(e)})
            return Response(
                {'error': 'Payment gateway communication failed'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Return payment details
        detail_serializer = PaymentDetailSerializer(payment)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class PaymentListView(generics.ListAPIView):
    """List user's payments."""
    serializer_class = PaymentListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self) -> QuerySet[Payment]: # type: ignore
        if not self.request.user.is_authenticated:
            return Payment.objects.none()
        return Payment.objects.filter(user=self.request.user).order_by('-created_at')

    @swagger_auto_schema(
        operation_description="List user's payments",
        responses={
            200: PaymentListSerializer(many=True),
            401: "Authentication required"
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)



class PaymentDetailView(generics.RetrieveAPIView):
    """Get payment details."""
    serializer_class = PaymentDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'order_id'
    
    def get_queryset(self) -> QuerySet[Payment]: # type: ignore
        if not self.request.user.is_authenticated:
            return Payment.objects.none()
        return Payment.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_description="Get payment details by order ID",
        responses={
            200: PaymentDetailSerializer,
            401: "Authentication required",
            404: "Payment not found"
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    
class PaymentVerifyView(generics.RetrieveAPIView):
    """Verify a payment using the ref_id."""
    serializer_class = PaymentDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "ref_id"
    
    def get_queryset(self) -> QuerySet[Payment]: # type: ignore
        if not self.request.user.is_authenticated:
            return Payment.objects.none()
        return Payment.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        payment = self.get_object()
        
        # If already successful, return current status
        if payment.status == Payment.SUCCESSFUL:
            return Response(self.get_serializer(payment).data)
        
        # If payment failed, don't retry verification
        if payment.status == Payment.FAILED:
            return Response(
                self.get_serializer(payment).data,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Only verify pending payments
        if payment.status != Payment.PENDING:
            return Response(self.get_serializer(payment).data)
        
        try:
            # Verify with gateway
            verification_result = MockGateway.verify_payment(payment.ref_id)
            
            if verification_result.get('status') == 'success':
                payment.mark_successful(
                    ref_id=payment.ref_id,
                    tracking_code=verification_result.get('tracking_code'),
                    response_data=verification_result
                )
            else:
                payment.mark_failed(response_data=verification_result)
                
        except Exception as e:
            # Gateway communication failed
            payment.gateway_response = {'verification_error': str(e)}
            payment.save()
            return Response(
                {'error': 'Payment verification failed'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return Response(self.get_serializer(payment).data)


class PaymentRefundView(generics.UpdateAPIView):
    """Refund a successful payment."""
    serializer_class = PaymentDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'order_id'
    
    def get_queryset(self) -> QuerySet[Payment]: # type: ignore
        if not self.request.user.is_authenticated:
            return Payment.objects.none()
        return Payment.objects.filter(
            user=self.request.user,
            status=Payment.SUCCESSFUL
        )

    @swagger_auto_schema(
        operation_description="Refund a successful payment",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'reason': openapi.Schema(type=openapi.TYPE_STRING, description='Refund reason')
            }
        ),
        responses={
            200: PaymentDetailSerializer,
            400: "Payment cannot be refunded",
            401: "Authentication required",
            404: "Payment not found"
        }
    )
    def patch(self, request, *args, **kwargs):
        payment = self.get_object()
        
        if not payment.can_be_refunded:
            return Response(
                {'error': 'Payment cannot be refunded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Process refund through gateway
            refund_result = MockGateway.refund_payment(
                ref_id=payment.ref_id,
                amount=payment.amount
            )
            
            if refund_result.get('status') == 'success':
                payment.mark_refunded(response_data=refund_result)
                return Response(self.get_serializer(payment).data)
            else:
                return Response(
                    {'error': 'Refund processing failed', 'details': refund_result},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            return Response(
                {'error': 'Refund service unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )