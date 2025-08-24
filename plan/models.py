from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from questionnaire.models import UserGoal
from payment.models import Payment
from decimal import Decimal

# =============== USER PROGRESS TRACKING ===============

class UserProgress(models.Model):
    """Track user progress through the entire flow"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='progress')
    
    STEP_CHOICES = [
        ('goal_selection', 'Goal Selection'),
        ('questionnaire', 'Questionnaire'),
        ('payment_pending', 'Payment Pending'),
        ('payment_completed', 'Payment Completed'),
        ('plan_generation', 'Plan Generation'),
        ('plan_ready', 'Plan Ready'),
        ('completed', 'Completed'),
    ]
    
    current_step = models.CharField(max_length=20, choices=STEP_CHOICES, default='goal_selection')
    completed_steps = models.JSONField(default=list)  # Track completed steps
    
    # Quick access to related objects
    selected_goal = models.ForeignKey(UserGoal, on_delete=models.SET_NULL, null=True, blank=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def mark_step_completed(self, step):
        """Mark a step as completed and move to next"""
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        
        # Define step progression
        step_progression = {
            'goal_selection': 'questionnaire',
            'questionnaire': 'payment_pending',
            'payment_pending': 'payment_completed',
            'payment_completed': 'plan_generation',
            'plan_generation': 'plan_ready',
            'plan_ready': 'completed'
        }
        
        if step in step_progression:
            self.current_step = step_progression[step]
        
        self.save()
    
    def can_access_step(self, step):
        """Check if user can access a particular step"""
        step_order = ['goal_selection', 'questionnaire', 'payment_pending', 
                     'payment_completed', 'plan_generation', 'plan_ready', 'completed']
        
        current_index = step_order.index(self.current_step)
        requested_index = step_order.index(step)
        
        return requested_index <= current_index
    
    def __str__(self):
        return f"{self.user.username} - {self.current_step}"


# =============== PLAN GENERATION TRACKING ===============

class PlanGeneration(models.Model):
    """Track plan generation from questionnaires - Enhanced version"""
    user_goal = models.OneToOneField(UserGoal, on_delete=models.CASCADE, related_name='plan_generation')
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)  # Link to payment
    
    # Generation status
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('queued', 'Queued for Generation'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # AI Integration fields
    ai_prompt_sent = models.TextField(blank=True)
    ai_response_raw = models.JSONField(default=dict, blank=True)
    ai_provider = models.CharField(max_length=50, default='openai')  # openai, claude, etc.
    
    # Generated plans (relationships)
    workout_plan = models.ForeignKey('WorkoutPlan', on_delete=models.SET_NULL, null=True, blank=True)
    diet_plan = models.ForeignKey('DietPlan', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Generation metadata
    algorithm_version = models.CharField(max_length=20, default='v1.0')
    generation_rules_applied = models.JSONField(default=dict, blank=True)
    processing_time_seconds = models.FloatField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    def can_retry(self):
        return self.retry_count < self.max_retries and self.status == 'failed'
    
    def __str__(self):
        return f"Generation for {self.user_goal} - {self.status}"


# =============== ENHANCED PLAN MODELS ===============

class WorkoutPlan(models.Model):
    """Enhanced WorkoutPlan with better AI integration"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workout_plans')
    user_goal = models.ForeignKey(UserGoal, on_delete=models.CASCADE, related_name='workout_plans')
    plan_generation = models.OneToOneField(PlanGeneration, on_delete=models.CASCADE, null=True, blank=True)
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Plan characteristics
    difficulty_level = models.CharField(max_length=20, choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ])
    
    duration_weeks = models.IntegerField(validators=[MinValueValidator(1)])
    sessions_per_week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(7)])
    
    # Structured workout data (from AI)
    workout_schedule = models.JSONField(default=dict, help_text="Weekly workout structure")
    exercises = models.JSONField(default=list, help_text="List of exercises with details")
    equipment_needed = models.JSONField(default=list)
    
    # AI generation info
    generated_from_ai = models.BooleanField(default=False)
    ai_confidence_score = models.FloatField(null=True, blank=True)  # If AI provides confidence
    
    # Metadata
    generation_algorithm_version = models.CharField(max_length=20, default='v1.0')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_weekly_schedule(self):
        """Helper method to get formatted weekly schedule"""
        return self.workout_schedule.get('weekly_schedule', {})
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"


class DietPlan(models.Model):
    """Enhanced DietPlan with better AI integration"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='diet_plans')
    user_goal = models.ForeignKey(UserGoal, on_delete=models.CASCADE, related_name='diet_plans')
    plan_generation = models.OneToOneField(PlanGeneration, on_delete=models.CASCADE, null=True, blank=True)
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Diet characteristics
    diet_type = models.CharField(max_length=20, choices=[
        ('balanced', 'Balanced Diet'),
        ('low_carb', 'Low Carb'),
        ('high_protein', 'High Protein'),
        ('keto', 'Ketogenic'),
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan'),
        ('mediterranean', 'Mediterranean'),
        ('intermittent_fasting', 'Intermittent Fasting'),
    ])
    
    # Nutritional targets
    daily_calorie_target = models.IntegerField(validators=[MinValueValidator(1000)])
    duration_weeks = models.IntegerField(validators=[MinValueValidator(1)])
    
    # Macro targets
    protein_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal(20.00))
    carb_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal(30.00))
    fat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal(50.00))
    
    # Structured meal data (from AI)
    meal_plan = models.JSONField(default=dict, help_text="Weekly meal plan structure")
    food_restrictions = models.JSONField(default=list)
    preferred_foods = models.JSONField(default=list)
    shopping_list = models.JSONField(default=list, help_text="Generated shopping list")
    
    # AI generation info
    generated_from_ai = models.BooleanField(default=False)
    ai_confidence_score = models.FloatField(null=True, blank=True)
    
    # Metadata
    generation_algorithm_version = models.CharField(max_length=20, default='v1.0')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_daily_macros(self):
        """Calculate daily macro targets in grams"""
        calories = self.daily_calorie_target
        return {
            'protein_grams': round((calories * float(self.protein_percentage) / 100) / 4),
            'carb_grams': round((calories * float(self.carb_percentage) / 100) / 4),
            'fat_grams': round((calories * float(self.fat_percentage) / 100) / 9),
        }
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"


# =============== USER PLAN SUMMARY ===============

class UserPlanSummary(models.Model):
    """Summary view of user's complete plan"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='plan_summary')
    user_goal = models.OneToOneField(UserGoal, on_delete=models.CASCADE)
    
    # Plan references
    diet_plan = models.OneToOneField(DietPlan, on_delete=models.CASCADE)
    workout_plan = models.OneToOneField(WorkoutPlan, on_delete=models.CASCADE)
    
    # Plan status
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(auto_now_add=True)
    
    # User feedback
    user_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], 
        null=True, blank=True
    )
    user_feedback = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Plan Summary"


# =============== RECOMMENDATION RULES (Your original) ===============

class RecommendationRule(models.Model):
    """Rules for generating plans based on questionnaire responses"""
    name = models.CharField(max_length=100)
    goal = models.ForeignKey('questionnaire.Goal', on_delete=models.CASCADE, related_name='recommendation_rules')
    
    # Conditions (stored as JSON for flexibility)
    conditions = models.JSONField(help_text="JSON conditions to match against answers")
    
    # Recommendations (stored as JSON)
    workout_recommendations = models.JSONField(default=dict, blank=True)
    diet_recommendations = models.JSONField(default=dict, blank=True)
    
    priority = models.IntegerField(default=0)  # Higher number = higher priority
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.goal.name} - {self.name}"


# =============== PLAN VERSIONING (Optional but useful) ===============

class PlanVersion(models.Model):
    """Track plan versions if user requests modifications"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan_type = models.CharField(max_length=20, choices=[
        ('diet', 'Diet Plan'),
        ('workout', 'Workout Plan'),
    ])
    
    version_number = models.IntegerField(default=1)
    plan_data = models.JSONField()  # Store the plan data
    
    # Reason for new version
    modification_reason = models.TextField(blank=True)
    modified_by_user = models.BooleanField(default=False)  # True if user requested changes
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'plan_type', 'version_number']
    
    def __str__(self):
        return f"{self.user.username} - {self.plan_type} v{self.version_number}"