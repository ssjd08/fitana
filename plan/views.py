# plan/views.py
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    UserProgress, PlanGeneration, WorkoutPlan, DietPlan, 
    UserPlanSummary, PlanVersion
)
from .serializers import (
    UserProgressSerializer, PlanGenerationSerializer, PlanGenerationCreateSerializer,
    WorkoutPlanSerializer, DietPlanSerializer, UserPlanSummarySerializer,
    UserPlanSummaryUpdateSerializer, WorkoutPlanListSerializer, DietPlanListSerializer,
    PlanVersionSerializer
)
from .tasks import generate_user_plan_async  # Celery task
from .services import PlanGenerationService, AIService
from questionnaire.models import UserGoal
from payment.models import Payment

User = get_user_model()


# =============== USER PROGRESS VIEWS ===============

class UserProgressView(APIView):
    """Get and update user progress"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get current user progress"""
        progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            defaults={'current_step': 'goal_selection'}
        )
        serializer = UserProgressSerializer(progress)
        return Response(serializer.data)
    
    def patch(self, request):
        """Update user progress (usually done by system)"""
        progress = get_object_or_404(UserProgress, user=request.user)
        
        # Only allow certain manual updates
        allowed_fields = ['user_feedback']  # Add fields users can manually update
        
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = UserProgressSerializer(progress, data=update_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =============== PLAN GENERATION VIEWS ===============

class PlanGenerationView(APIView):
    """Handle plan generation requests"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get plan generation status"""
        try:
            user_goal = UserGoal.objects.get(user=request.user, is_completed=True)
            plan_generation = get_object_or_404(PlanGeneration, user_goal=user_goal)
            serializer = PlanGenerationSerializer(plan_generation)
            return Response(serializer.data)
        except UserGoal.DoesNotExist:
            return Response({
                'error': 'No completed questionnaire found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def post(self, request):
        """Start plan generation process"""
        try:
            # Get user's completed questionnaire and payment
            user_goal = UserGoal.objects.get(user=request.user, is_completed=True)
            
            # Check if user has valid payment
            payment = Payment.objects.filter(
                user=request.user, 
                status='completed'
            ).order_by('-created_at').first()
            
            if not payment:
                return Response({
                    'error': 'No valid payment found'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if plan generation already exists
            if hasattr(user_goal, 'plan_generation'):
                return Response({
                    'error': 'Plan generation already exists',
                    'plan_generation_id': user_goal.plan_generation.id # type: ignore
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create plan generation record
            with transaction.atomic():
                plan_generation = PlanGeneration.objects.create(
                    user_goal=user_goal,
                    payment=payment,
                    status='queued',
                    queued_at=timezone.now()
                )
                
                # Update user progress
                progress = UserProgress.objects.get(user=request.user)
                progress.mark_step_completed('payment_completed')
            
            # Start async plan generation
            generate_user_plan_async.delay(plan_generation.id)
            
            serializer = PlanGenerationSerializer(plan_generation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except UserGoal.DoesNotExist:
            return Response({
                'error': 'No completed questionnaire found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Plan generation failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RetryPlanGenerationView(APIView):
    """Retry failed plan generation"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, generation_id):
        """Retry plan generation"""
        plan_generation = get_object_or_404(
            PlanGeneration, 
            id=generation_id,
            user_goal__user=request.user
        )
        
        if not plan_generation.can_retry():
            return Response({
                'error': 'Cannot retry plan generation. Max retries exceeded or status not failed.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset status and retry
        plan_generation.status = 'queued'
        plan_generation.queued_at = timezone.now()
        plan_generation.error_message = ''
        plan_generation.retry_count += 1
        plan_generation.save()
        
        # Start async generation again
        generate_user_plan_async.delay(plan_generation.id)
        
        serializer = PlanGenerationSerializer(plan_generation)
        return Response(serializer.data)


# =============== PLAN VIEWS ===============

class UserPlanSummaryView(APIView):
    """Get user's complete plan summary"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user's plan summary"""
        try:
            plan_summary = UserPlanSummary.objects.get(user=request.user, is_active=True)
            serializer = UserPlanSummarySerializer(plan_summary)
            
            # Update progress if user is viewing plan for first time
            progress = UserProgress.objects.get(user=request.user)
            if progress.current_step == 'plan_ready':
                progress.mark_step_completed('plan_ready')
            
            return Response(serializer.data)
            
        except UserPlanSummary.DoesNotExist:
            return Response({
                'error': 'No active plan found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def patch(self, request):
        """Update plan rating/feedback"""
        try:
            plan_summary = UserPlanSummary.objects.get(user=request.user, is_active=True)
            serializer = UserPlanSummaryUpdateSerializer(plan_summary, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except UserPlanSummary.DoesNotExist:
            return Response({
                'error': 'No active plan found'
            }, status=status.HTTP_404_NOT_FOUND)


class WorkoutPlanDetailView(generics.RetrieveAPIView):
    """Get detailed workout plan"""
    serializer_class = WorkoutPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return get_object_or_404(
            WorkoutPlan, 
            user=self.request.user,
            is_active=True
        )


class DietPlanDetailView(generics.RetrieveAPIView):
    """Get detailed diet plan"""
    serializer_class = DietPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return get_object_or_404(
            DietPlan, 
            user=self.request.user,
            is_active=True
        )


# =============== PLAN HISTORY VIEWS ===============

class UserWorkoutPlansView(generics.ListAPIView):
    """List user's workout plans"""
    serializer_class = WorkoutPlanListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return WorkoutPlan.objects.filter(user=self.request.user).order_by('-created_at')


class UserDietPlansView(generics.ListAPIView):
    """List user's diet plans"""
    serializer_class = DietPlanListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DietPlan.objects.filter(user=self.request.user).order_by('-created_at')


# =============== PLAN VERSION VIEWS ===============

class PlanVersionListView(generics.ListAPIView):
    """List plan versions for a user"""
    serializer_class = PlanVersionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        plan_type = self.request.query_params.get('plan_type', 'diet')
        return PlanVersion.objects.filter(
            user=self.request.user,
            plan_type=plan_type
        ).order_by('-version_number')


# =============== UTILITY VIEWS ===============

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def request_plan_modification(request):
    """Request plan modification"""
    try:
        plan_summary = UserPlanSummary.objects.get(user=request.user, is_active=True)
        modification_request = request.data.get('modification_request', '')
        plan_type = request.data.get('plan_type', 'diet')  # 'diet' or 'workout'
        
        if not modification_request:
            return Response({
                'error': 'Modification request is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create new plan version request (you might want to handle this async)
        # For now, we'll just log the request
        PlanVersion.objects.create(
            user=request.user,
            plan_type=plan_type,
            plan_data={'modification_request': modification_request},
            modification_reason=modification_request,
            modified_by_user=True,
            is_current=False  # Will become current after processing
        )
        
        return Response({
            'message': 'Modification request submitted successfully',
            'estimated_processing_time': '24-48 hours'
        })
        
    except UserPlanSummary.DoesNotExist:
        return Response({
            'error': 'No active plan found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def plan_statistics(request):
    """Get plan statistics for user"""
    try:
        plan_summary = UserPlanSummary.objects.get(user=request.user, is_active=True)
        
        stats = {
            'plan_created': plan_summary.created_at,
            'days_since_creation': (timezone.now().date() - plan_summary.start_date).days,
            'diet_plan': {
                'daily_calories': plan_summary.diet_plan.daily_calorie_target,
                'duration_weeks': plan_summary.diet_plan.duration_weeks,
                'diet_type': plan_summary.diet_plan.diet_type,
            },
            'workout_plan': {
                'sessions_per_week': plan_summary.workout_plan.sessions_per_week,
                'duration_weeks': plan_summary.workout_plan.duration_weeks,
                'difficulty': plan_summary.workout_plan.difficulty_level,
                'total_exercises': len(plan_summary.workout_plan.exercises) if plan_summary.workout_plan.exercises else 0
            },
            'user_feedback': {
                'rating': plan_summary.user_rating,
                'has_feedback': bool(plan_summary.user_feedback),
            }
        }
        
        return Response(stats)
        
    except UserPlanSummary.DoesNotExist:
        return Response({
            'error': 'No active plan found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cancel_plan_generation(request):
    """Cancel ongoing plan generation"""
    try:
        user_goal = UserGoal.objects.get(user=request.user, is_completed=True)
        plan_generation = get_object_or_404(PlanGeneration, user_goal=user_goal)
        
        if plan_generation.status not in ['queued', 'processing']:
            return Response({
                'error': 'Cannot cancel plan generation in current status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        plan_generation.status = 'cancelled'
        plan_generation.save()
        
        # Update user progress back to payment completed
        progress = UserProgress.objects.get(user=request.user)
        progress.current_step = 'payment_completed'
        progress.save()
        
        return Response({
            'message': 'Plan generation cancelled successfully'
        })
        
    except UserGoal.DoesNotExist:
        return Response({
            'error': 'No questionnaire found'
        }, status=status.HTTP_404_NOT_FOUND)


# =============== ADMIN/TESTING VIEWS ===============

class ForceCompleteGenerationView(APIView):
    """Force complete plan generation (for testing/admin)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, generation_id):
        """Force complete generation with dummy data"""
        if not request.user.is_staff:  # Only staff can use this
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        plan_generation = get_object_or_404(PlanGeneration, id=generation_id)
        
        # Use the service to create dummy plans
        try:
            PlanGenerationService.create_dummy_plans(plan_generation)
            return Response({
                'message': 'Plan generation completed with dummy data'
            })
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)