from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.db.models import QuerySet
from django.conf import settings
from django.shortcuts import render
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Payment
from .serializers import PaymentCreateSerializer, PaymentDetailSerializer
from .gateways import ZarinPalGateway, MockGateway


def get_payment_gateway():
    """
    Factory function to get the appropriate payment gateway.
    Configure in settings.py with PAYMENT_GATEWAY setting.
    """
    gateway_type = getattr(settings, 'PAYMENT_GATEWAY', 'zarinpal').lower()
    
    if gateway_type == 'mock':
        return MockGateway()
    else:
        return ZarinPalGateway()

class PaymentCreateView(generics.CreateAPIView):
    """Create payment and redirect to ZarinPal gateway."""
    serializer_class = PaymentCreateSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new payment and get ZarinPal redirect URL",
        responses={
            201: openapi.Response(
                description="Payment created successfully",
                examples={
                    "application/json": {
                        "payment": {
                            "id": 1,
                            "order_id": "123e4567-e89b-12d3-a456-426614174000",
                            "amount": "50000",
                            "currency": "IRR",
                            "status": "pending"
                        },
                        "payment_url": "https://www.zarinpal.com/pg/StartPay/A00000000000000000000000000123456789",
                        "message": "Redirect user to payment_url to complete payment"
                    }
                }
            ),
            400: "Validation errors",
            401: "Authentication required",
            503: "Gateway communication failed"
        }
    )
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create payment and get ZarinPal redirect URL."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Auto-generate description
        amount = serializer.validated_data['amount']
        currency = serializer.validated_data.get('currency', 'IRR')
        current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        description = f"User with id {request.user.id} paying {amount} {currency} on {current_time}"
        
        # Create payment with pending status
        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            currency=currency,
            description=description,
            status=Payment.PENDING,
            gateway='ZarinPal'
        )
        
        try:
            # Initialize ZarinPal gateway
            gateway = ZarinPalGateway()
            
            # Request payment from ZarinPal
            gateway_response = gateway.request_payment(
                amount=int(payment.amount),
                description=payment.description,
                mobile=request.user.phone if hasattr(request.user, 'phone') else None,
                email=request.user.email if request.user.email else None
            )
            
            # Store gateway response
            payment.gateway_response = gateway_response
            
            if gateway_response.get('success'):
                # Store authority for verification later
                payment.gateway_authority = gateway_response.get('authority')
                payment.save()
                
                # Return payment details with redirect URL
                return Response({
                    'payment': PaymentDetailSerializer(payment).data,
                    'payment_url': gateway_response.get('payment_url'),
                    'authority': gateway_response.get('authority'),
                    'message': 'Redirect user to payment_url to complete payment'
                }, status=status.HTTP_201_CREATED)
            else:
                # ZarinPal returned error
                payment.mark_failed(response_data=gateway_response)
                return Response({
                    'error': 'Failed to initialize payment',
                    'details': gateway_response.get('error'),
                    'code': gateway_response.get('code')
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            # Gateway communication failed
            payment.mark_failed(response_data={'error': str(e)})
            return Response(
                {'error': 'Payment gateway communication failed', 'details': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class PaymentVerifyView(generics.GenericAPIView):
    """Verify payment callback from ZarinPal."""
    permission_classes = []  # Allow public access for gateway callbacks
    
    @swagger_auto_schema(
        operation_description="Verify payment after redirect from ZarinPal",
        manual_parameters=[
            openapi.Parameter(
                'Authority', 
                openapi.IN_QUERY, 
                type=openapi.TYPE_STRING, 
                required=True,
                description="Authority code from ZarinPal"
            ),
            openapi.Parameter(
                'Status', 
                openapi.IN_QUERY, 
                type=openapi.TYPE_STRING, 
                required=True,
                description="Payment status (OK or NOK)"
            ),
        ],
        responses={
            200: openapi.Response(
                description="Payment verified successfully",
                examples={
                    "application/json": {
                        "success": True,
                        "message": "Payment verified successfully",
                        "ref_id": "123456789",
                        "payment": {
                            "order_id": "123e4567-e89b-12d3-a456-426614174000",
                            "amount": "50000",
                            "status": "successful"
                        }
                    }
                }
            ),
            400: "Payment verification failed or cancelled",
            404: "Payment not found"
        }
    )
    def get(self, request):
        """Handle ZarinPal callback (GET request)."""
        authority = request.query_params.get('Authority')
        status_param = request.query_params.get('Status')
        
        if not authority:
            return Response(
                {'success': False, 'error': 'Authority parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find payment by authority (removed user filter for public callback)
        try:
            payment = Payment.objects.get(gateway_authority=authority)
        except Payment.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user cancelled payment
        if status_param != 'OK':
            payment.mark_cancelled(response_data={
                'status': status_param,
                'message': 'Payment cancelled by user'
            })
            return Response({
                'success': False,
                'message': 'Payment was cancelled by user',
                'payment': PaymentDetailSerializer(payment).data
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify payment with gateway
        try:
            gateway = get_payment_gateway()
            verify_response = gateway.verify_payment(
                authority=authority,
                amount=int(payment.amount)
            )
            
            if verify_response.get('success'):
                # Payment verified successfully
                ref_id = verify_response.get('ref_id')
                card_pan = verify_response.get('card_pan', '')
                
                payment.mark_successful(
                    ref_id=ref_id,
                    tracking_code=ref_id,  # ZarinPal uses ref_id as tracking
                    response_data=verify_response
                )
                
                # Mask and store card number if provided
                if card_pan:
                    payment.card_number_masked = Payment.mask_card_number(card_pan)
                    payment.save()
                
                return Response({
                    'success': True,
                    'message': verify_response.get('message', 'Payment verified successfully'),
                    'ref_id': ref_id,
                    'card_pan': card_pan[-4:] if card_pan else None,
                    'payment': PaymentDetailSerializer(payment).data
                }, status=status.HTTP_200_OK)
            else:
                # Verification failed
                payment.mark_failed(response_data=verify_response)
                return Response({
                    'success': False,
                    'error': 'Payment verification failed',
                    'details': verify_response.get('error'),
                    'code': verify_response.get('code'),
                    'payment': PaymentDetailSerializer(payment).data
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            payment.mark_failed(response_data={'error': str(e)})
            return Response({
                'success': False,
                'error': 'Verification process failed',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class PaymentListView(generics.ListAPIView):
    """List user's payments."""
    serializer_class = PaymentDetailSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self) -> QuerySet[Payment]: # type: ignore
        """Return payments for current user."""
        return Payment.objects.filter(user=self.request.user).order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="Get list of user's payments",
        manual_parameters=[
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by payment status (pending, successful, failed, cancelled)"
            )
        ]
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PaymentDetailView(generics.RetrieveAPIView):
    """Get payment details."""
    serializer_class = PaymentDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'order_id'
    
    def get_queryset(self) -> QuerySet[Payment]: # type: ignore
        """Return payments for current user."""
        return Payment.objects.filter(user=self.request.user)
        
        
# class PaymentRefundView(generics.UpdateAPIView):
#     """Refund a successful payment."""
#     serializer_class = PaymentDetailSerializer
#     permission_classes = [IsAuthenticated]
#     lookup_field = 'order_id'
    
#     def get_queryset(self) -> QuerySet[Payment]: # type: ignore
#         if not self.request.user.is_authenticated:
#             return Payment.objects.none()
#         return Payment.objects.filter(
#             user=self.request.user,
#             status=Payment.SUCCESSFUL
#         )

#     @swagger_auto_schema(
#         operation_description="Refund a successful payment",
#         request_body=openapi.Schema(
#             type=openapi.TYPE_OBJECT,
#             properties={
#                 'reason': openapi.Schema(type=openapi.TYPE_STRING, description='Refund reason')
#             }
#         ),
#         responses={
#             200: PaymentDetailSerializer,
#             400: "Payment cannot be refunded",
#             401: "Authentication required",
#             404: "Payment not found"
#         }
#     )
#     def patch(self, request, *args, **kwargs):
#         payment = self.get_object()
        
#         if not payment.can_be_refunded:
#             return Response(
#                 {'error': 'Payment cannot be refunded'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         try:
#             # Process refund through gateway
#             refund_result = MockGateway.refund_payment(
#                 ref_id=payment.ref_id,
#                 amount=payment.amount
#             )
            
#             if refund_result.get('status') == 'success':
#                 payment.mark_refunded(response_data=refund_result)
#                 return Response(self.get_serializer(payment).data)
#             else:
#                 return Response(
#                     {'error': 'Refund processing failed', 'details': refund_result},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
                
#         except Exception as e:
#             return Response(
#                 {'error': 'Refund service unavailable'},
#                 status=status.HTTP_503_SERVICE_UNAVAILABLE
#             )