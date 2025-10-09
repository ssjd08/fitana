# plan/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    UserProgress, PlanGeneration, WorkoutPlan, DietPlan, 
    UserPlanSummary, RecommendationRule, PlanVersion
)
from questionnaire.models import UserGoal
from payment.models import Payment

User = get_user_model()


# =============== USER PROGRESS SERIALIZERS ===============

class UserProgressSerializer(serializers.ModelSerializer):
    """Serializer for user progress tracking"""
    can_proceed = serializers.SerializerMethodField()
    next_step_url = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProgress
        fields = [
            'current_step', 'completed_steps', 'can_proceed', 
            'next_step_url', 'progress_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_can_proceed(self, obj):
        """Check if user can proceed to next step"""
        step_requirements = {
            'goal_selection': True,  # Always can start
            'questionnaire': obj.selected_goal is not None,
            'payment_pending': 'questionnaire' in obj.completed_steps,
            'payment_completed': obj.payment is not None and obj.payment.status == 'completed',
            'plan_generation': obj.payment is not None and obj.payment.status == 'completed',
            'plan_ready': hasattr(obj, 'selected_goal') and hasattr(obj.selected_goal, 'plan_generation'),
            'completed': True,
        }
        return step_requirements.get(obj.current_step, False)
    
    def get_next_step_url(self, obj):
        """Get URL for next step"""
        step_urls = {
            'goal_selection': '/questionnaire/goals/',
            'questionnaire': '/questionnaire/questions/',
            'payment_pending': '/payment/plans/',
            'payment_completed': '/plans/generate/',
            'plan_generation': '/plans/status/',
            'plan_ready': '/plans/my-plan/',
            'completed': '/plans/my-plan/',
        }
        return step_urls.get(obj.current_step)
    
    def get_progress_percentage(self, obj):
        """Calculate progress percentage"""
        all_steps = ['goal_selection', 'questionnaire', 'payment_pending', 
                    'payment_completed', 'plan_generation', 'plan_ready', 'completed']
        
        try:
            current_index = all_steps.index(obj.current_step)
            return round((current_index / (len(all_steps) - 1)) * 100, 1)
        except ValueError:
            return 0


# =============== PLAN GENERATION SERIALIZERS ===============

class PlanGenerationSerializer(serializers.ModelSerializer):
    """Serializer for plan generation tracking"""
    user_goal_name = serializers.CharField(source='user_goal.goal.name', read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    estimated_completion = serializers.SerializerMethodField()
    can_retry = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PlanGeneration
        fields = [
            'id', 'status', 'user_goal_name', 'payment_status', 
            'estimated_completion', 'can_retry', 'error_message',
            'retry_count', 'processing_time_seconds',
            'created_at', 'started_at', 'completed_at'
        ]
        read_only_fields = [
            'created_at', 'started_at', 'completed_at', 
            'processing_time_seconds', 'retry_count'
        ]
    
    def get_estimated_completion(self, obj):
        """Estimate completion time based on status"""
        if obj.status == 'completed':
            return None
        elif obj.status == 'processing':
            return "2-3 minutes"
        elif obj.status == 'queued':
            return "5-10 minutes"
        else:
            return None


class PlanGenerationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating plan generation"""
    
    class Meta:
        model = PlanGeneration
        fields = ['user_goal', 'payment']
    
    def validate(self, attrs):
        """Validate plan generation creation"""
        user_goal = attrs['user_goal']
        payment = attrs['payment']
        
        # Check if user owns the goal and payment
        request_user = self.context['request'].user
        if user_goal.user != request_user:
            raise serializers.ValidationError("You don't own this goal")
        
        if payment.user != request_user:
            raise serializers.ValidationError("You don't own this payment")
        
        # Check if payment is completed
        if payment.status != 'completed':
            raise serializers.ValidationError("Payment must be completed")
        
        # Check if generation already exists
        if hasattr(user_goal, 'plan_generation'):
            raise serializers.ValidationError("Plan generation already exists for this goal")
        
        return attrs


# =============== PLAN SERIALIZERS ===============

class WorkoutPlanSerializer(serializers.ModelSerializer):
    """Serializer for workout plans"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    goal_name = serializers.CharField(source='user_goal.goal.name', read_only=True)
    weekly_schedule = serializers.SerializerMethodField()
    total_exercises = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkoutPlan
        fields = [
            'id', 'name', 'description', 'user_name', 'goal_name',
            'difficulty_level', 'duration_weeks', 'sessions_per_week',
            'workout_schedule', 'exercises', 'equipment_needed',
            'weekly_schedule', 'total_exercises', 'generated_from_ai',
            'ai_confidence_score', 'created_at'
        ]
        read_only_fields = ['created_at', 'generated_from_ai', 'ai_confidence_score']
    
    def get_weekly_schedule(self, obj):
        """Get formatted weekly schedule"""
        return obj.get_weekly_schedule()
    
    def get_total_exercises(self, obj):
        """Count total exercises in the plan"""
        return len(obj.exercises) if obj.exercises else 0


class DietPlanSerializer(serializers.ModelSerializer):
    """Serializer for diet plans"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    goal_name = serializers.CharField(source='user_goal.goal.name', read_only=True)
    daily_macros = serializers.SerializerMethodField()
    weekly_meal_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DietPlan
        fields = [
            'id', 'name', 'description', 'user_name', 'goal_name',
            'diet_type', 'daily_calorie_target', 'duration_weeks',
            'protein_percentage', 'carb_percentage', 'fat_percentage',
            'meal_plan', 'food_restrictions', 'preferred_foods', 'shopping_list',
            'daily_macros', 'weekly_meal_count', 'generated_from_ai',
            'ai_confidence_score', 'created_at'
        ]
        read_only_fields = ['created_at', 'generated_from_ai', 'ai_confidence_score']
    
    def get_daily_macros(self, obj):
        """Get daily macro targets in grams"""
        return obj.get_daily_macros()
    
    def get_weekly_meal_count(self, obj):
        """Count meals in weekly plan"""
        if not obj.meal_plan or 'weekly_meals' not in obj.meal_plan:
            return 0
        return len(obj.meal_plan['weekly_meals'])


# =============== SUMMARY SERIALIZERS ===============

class UserPlanSummarySerializer(serializers.ModelSerializer):
    """Complete user plan summary"""
    diet_plan = DietPlanSerializer(read_only=True)
    workout_plan = WorkoutPlanSerializer(read_only=True)
    goal_name = serializers.CharField(source='user_goal.goal.name', read_only=True)
    plan_duration_weeks = serializers.SerializerMethodField()
    
    class Meta:
        model = UserPlanSummary
        fields = [
            'id', 'goal_name', 'diet_plan', 'workout_plan',
            'plan_duration_weeks', 'is_active', 'start_date',
            'user_rating', 'user_feedback', 'created_at'
        ]
    
    def get_plan_duration_weeks(self, obj):
        """Get the plan duration (max of diet/workout)"""
        diet_weeks = obj.diet_plan.duration_weeks if obj.diet_plan else 0
        workout_weeks = obj.workout_plan.duration_weeks if obj.workout_plan else 0
        return max(diet_weeks, workout_weeks)


class UserPlanSummaryUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating plan summary (rating/feedback)"""
    
    class Meta:
        model = UserPlanSummary
        fields = ['user_rating', 'user_feedback']
    
    def validate_user_rating(self, value):
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value


# =============== PLAN VERSION SERIALIZERS ===============

class PlanVersionSerializer(serializers.ModelSerializer):
    """Serializer for plan versions"""
    
    class Meta:
        model = PlanVersion
        fields = [
            'id', 'plan_type', 'version_number', 'plan_data',
            'modification_reason', 'modified_by_user', 
            'created_at', 'is_current'
        ]
        read_only_fields = ['created_at']


# =============== LIGHTWEIGHT SERIALIZERS FOR LISTS ===============

class WorkoutPlanListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for workout plan lists"""
    goal_name = serializers.CharField(source='user_goal.goal.name', read_only=True)
    
    class Meta:
        model = WorkoutPlan
        fields = [
            'id', 'name', 'goal_name', 'difficulty_level', 
            'duration_weeks', 'sessions_per_week', 'created_at'
        ]


class DietPlanListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for diet plan lists"""
    goal_name = serializers.CharField(source='user_goal.goal.name', read_only=True)
    
    class Meta:
        model = DietPlan
        fields = [
            'id', 'name', 'goal_name', 'diet_type', 
            'daily_calorie_target', 'duration_weeks', 'created_at'
        ]


# =============== RECOMMENDATION RULE SERIALIZERS ===============

class RecommendationRuleSerializer(serializers.ModelSerializer):
    """Serializer for recommendation rules (admin use)"""
    goal_name = serializers.CharField(source='goal.name', read_only=True)
    
    class Meta:
        model = RecommendationRule
        fields = [
            'id', 'name', 'goal_name', 'conditions',
            'workout_recommendations', 'diet_recommendations',
            'priority', 'is_active'
        ]