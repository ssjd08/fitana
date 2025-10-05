from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView
from django.db.models import QuerySet
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.request import Request
from typing import Any
import json


from .serializers import (
    GoalSerializer, 
    GoalWithQuestionsSerializer, 
    QuestionSerializer,
    AnonymousQuestionnaireSerializer,
    CompleteRegistrationSerializer
)
from .models import Goal, Question, Answer, UserGoal
from accounts.serializers import UserSerializer
from accounts.serializers import VerifyOTPSerializer
from accounts.serializers import SendOTPSerializer



class GoalListCreateView(ListCreateAPIView):
    """
    List all goals or create a new goal.
    Only admins can create goals.
    """
    serializer_class = GoalSerializer
    
    def get_queryset(self) -> QuerySet[Goal]:# type: ignore
        # Only return active goals for regular users
        if hasattr(self.request.user, 'is_staff') and self.request.user.is_staff:
            return Goal.objects.all()
        return Goal.objects.filter(is_active=True)
    
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminUser()]
        return [AllowAny()]


class GoalDetailView(RetrieveAPIView):
    """
    Retrieve a goal with all its associated questions and choices.
    """
    serializer_class = GoalWithQuestionsSerializer
    lookup_field = 'pk'
    
    def get_queryset(self) -> QuerySet[Goal]:# type: ignore
        return Goal.objects.prefetch_related(
            "questions__choices"
        ).filter(is_active=True)


class QuestionListCreateView(ListCreateAPIView):
    """
    List all questions or create a new question.
    Only admins can create questions.
    """
    serializer_class = QuestionSerializer
    
    def get_queryset(self) -> QuerySet[Question]:# type: ignore
        queryset = Question.objects.select_related('goal').prefetch_related('choices')
        
        # Filter by goal if provided
        if hasattr(self.request, 'query_params'):
            goal_id = self.request.query_params.get('goal')  # type: ignore
            if goal_id:
                queryset = queryset.filter(goal_id=goal_id)
            
        return queryset.order_by('order')
    
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminUser()]
        return [AllowAny()]


class QuestionDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a question with all its choices.
    """
    serializer_class = QuestionSerializer
    queryset = Question.objects.prefetch_related('choices').all()
    lookup_field = 'pk'
    
    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAdminUser()]
        return [AllowAny()]

    
class QuestionnaireSubmitWithOTPView(APIView):
    """
    Submit questionnaire data and automatically send OTP for verification.
    This combines questionnaire submission with OTP sending in a single request.
    """
    permission_classes = []  # No authentication required

    @swagger_auto_schema(
        request_body=AnonymousQuestionnaireSerializer,
        responses={
            201: openapi.Response(
                description="Questionnaire data saved and OTP sent",
                examples={
                    "application/json": {
                        "message": "Questionnaire data saved and OTP sent to your phone.",
                        "session_id": "123e4567-e89b-12d3-a456-426614174000",
                        "phone": "09123456789",
                        "goal_id": 1,
                        "answers_count": 3,
                        "otp_sent": True,
                        "next_step": "otp_verification",
                        "instructions": "Enter the OTP code sent to your phone to complete registration"
                    }
                }
            ),
            400: "Validation errors"
        },
        operation_description="""
        Submit questionnaire answers and automatically send OTP for phone verification. 

        This endpoint will:
        1. Validate and temporarily store questionnaire data
        2. Send OTP to the provided phone number
        3. Return session_id for completing registration

        Request format:
        {
            "goal_id": 1,
            "phone": "09123456789",
            "answers": [
                {
                    "question": 1,
                    "choice_answer": 1
                },
                {
                    "question": 2,
                    "text_answer": "John Doe"
                }
            ],
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com"
        }
        """
    )
    def post(self, request):
        # 1. Validate & save questionnaire
        serializer = AnonymousQuestionnaireSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        questionnaire_result = serializer.save()  # dict with session_id, phone, goal_id, answers_count

        # 2. Extract phone number
        phone = questionnaire_result['phone'] # type: ignore

        # 3. Send OTP
        otp_serializer = SendOTPSerializer(data={'phone': phone})
        if not otp_serializer.is_valid():
            return Response(otp_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        otp_serializer.save()

        # 4. Return response
        return Response({
            "message": "Questionnaire data saved. Please verify your phone number to complete registration.",
            "session_id": questionnaire_result['session_id'], # type: ignore
            "phone": phone,
            "goal_id": questionnaire_result['goal_id'], # type: ignore
            "answers_count": questionnaire_result['answers_count'], # type: ignore
            "otp_sent": True,
            "next_step": "phone_verification",
            "instructions": {
                "step_1": "Verify OTP: POST /auth/verify-otp/ with phone, code, and session_id",
                "step_2": "Your questionnaire data will be automatically saved to your account"
            }
        }, status=status.HTTP_201_CREATED)


class QuestionnaireStatusView(APIView):
    """
    Check the status of a questionnaire session
    """
    permission_classes = []
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'session_id',
                openapi.IN_QUERY,
                description="Session ID from questionnaire submission",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: "Session status",
            404: "Session not found"
        }
    )
    def get(self, request):
        session_id = request.query_params.get('session_id')
        
        if not session_id:
            return Response({
                "error": "session_id parameter is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        cache_key = f"questionnaire_session_{session_id}"
        cached_data_str = cache.get(cache_key)
        
        if not cached_data_str:
            return Response({
                "error": "Session not found or expired",
                "message": "Please submit questionnaire again"
            }, status=status.HTTP_404_NOT_FOUND)
        
        cached_data = json.loads(cached_data_str)
        
        # Try to get TTL, fallback if not supported
        try:
            expires_in_minutes = cache.ttl(cache_key) // 60  # type: ignore
        except AttributeError:
            # TTL not supported by this cache backend
            # Calculate approximate remaining time based on creation time
            from datetime import datetime
            created_at = datetime.fromisoformat(cached_data['created_at'])
            current_time = timezone.now()
            elapsed_minutes = (current_time - created_at).total_seconds() // 60
            expires_in_minutes = max(0, 60 - elapsed_minutes)  # Assuming 1 hour timeout
        except Exception:
            # Fallback if TTL calculation fails
            expires_in_minutes = None
        
        response_data = {
            "session_id": session_id,
            "phone": cached_data['phone'],
            "goal_id": cached_data['goal_id'],
            "answers_count": len(cached_data['answers']),
            "created_at": cached_data['created_at'],
            "status": "pending_verification"
        }
        
        if expires_in_minutes is not None:
            response_data["expires_in_minutes"] = expires_in_minutes
        
        return Response(response_data)
    

class EnhancedVerifyOTPView(APIView):
    """
    Enhanced OTP verification that completes questionnaire registration
    """
    
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone', 'code'],
            properties={
                'phone': openapi.Schema(type=openapi.TYPE_STRING, description='Phone number'),
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='OTP code'),
                'session_id': openapi.Schema(type=openapi.TYPE_STRING, description='Questionnaire session ID (optional)'),
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Desired username (optional)'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Password (required for new users)'),
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='Email (optional)'),
                'first_name': openapi.Schema(type=openapi.TYPE_STRING, description='First name (optional)'),
                'last_name': openapi.Schema(type=openapi.TYPE_STRING, description='Last name (optional)'),
            }
        ),
        responses={
            200: "OTP verified and questionnaire completed",
            400: "Validation errors"
        }
    )
    def post(self, request):
        
        # First verify OTP using existing logic
        otp_serializer = VerifyOTPSerializer(data=request.data)
        
        if not otp_serializer.is_valid():
            return Response(otp_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Process OTP verification
        result = otp_serializer.save()
        user = result['user'] # type: ignore
        is_new = result['is_new'] # type: ignore
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        response_data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "is_new": is_new,
            "user": UserSerializer(user).data
        }
        
        # Check if there's a questionnaire session to complete
        session_id = request.data.get('session_id')
        if session_id:
            try:
                complete_serializer = CompleteRegistrationSerializer(
                    data={'session_id': session_id}
                )
                if complete_serializer.is_valid():
                    questionnaire_result = complete_serializer.complete_registration(user) # type: ignore
                    response_data.update({
                        "questionnaire_completed": True,
                        "questionnaire_data": questionnaire_result
                    })
                else:
                    response_data.update({
                        "questionnaire_completed": False,
                        "questionnaire_error": complete_serializer.errors
                    })
            except Exception as e:
                response_data.update({
                    "questionnaire_completed": False,
                    "questionnaire_error": str(e)
                })
        
        return Response(response_data, status=status.HTTP_200_OK)