from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, SendOTPSerializer, VerifyOTPSerializer
from .models import PhoneOTP
from typing import Dict, Any

User = get_user_model()


class SendOTPView(APIView):
    """
    Send OTP to phone number for verification
    """
    
    @swagger_auto_schema(
        request_body=SendOTPSerializer,
        responses={
            200: openapi.Response(
                description="OTP sent successfully",
                examples={
                    "application/json": {
                        "detail": "OTP sent successfully",
                        "session_id": "123e4567-e89b-12d3-a456-426614174000"
                    }
                }
            ),
            400: "Invalid phone number format"
        },
        operation_description="Send OTP code to the provided phone number"
    )
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    """
    Verify OTP and login/register user
    """
    
    @swagger_auto_schema(
        request_body=VerifyOTPSerializer,
        responses={
            200: openapi.Response(
                description="OTP verified successfully",
                examples={
                    "application/json": {
                        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "is_new": True,
                        "user": {
                            "id": 1,
                            "username": "09123456789",
                            "first_name": "John",
                            "last_name": "Doe",
                            "email": "john@example.com",
                            "phone": "09123456789",
                            "membership": "B"
                        }
                    }
                }
            ),
            400: "Invalid OTP or validation errors"
        },
        operation_description="Verify OTP code and authenticate/register user"
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result: Dict[str, Any] = serializer.save() # type: ignore
        
        user = result['user']
        is_new: bool = result['is_new']
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Serialize user data
        user_serializer = UserSerializer(user)
        
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "is_new": is_new,
            "user": user_serializer.data
        }, status=status.HTTP_200_OK)


class MeView(APIView):
    """
    Get and update current user profile
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        responses={
            200: UserSerializer,
            401: "Authentication required"
        },
        operation_description="Get current user profile"
    )
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        request_body=UserSerializer,
        responses={
            200: UserSerializer,
            400: "Validation errors",
            401: "Authentication required"
        },
        operation_description="Update current user profile"
    )
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    Logout user by blacklisting refresh token
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token to blacklist')
            },
            required=['refresh']
        ),
        responses={
            200: "Successfully logged out",
            400: "Invalid token"
        },
        operation_description="Logout user by blacklisting refresh token"
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {"detail": "Successfully logged out"}, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            # More detailed error for debugging
            return Response(
                {
                    "error": "Invalid token",
                    "detail": str(e) if hasattr(e, 'args') else "Token blacklisting failed"
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )