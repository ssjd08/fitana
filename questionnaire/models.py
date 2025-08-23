from django.db import models
from django.conf import settings


# Create your models here.
class Goal(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=[
        ('weight_loss', 'Weight Loss'),
        ('weight_gain', 'Weight Gain'),
        ('muscle_gain', 'Muscle Gain'),
        ('endurance', 'Endurance'),
        ('strength', 'Strength'),
        ('general_fitness', 'General Fitness'),
    ], default='general_fitness')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
class Question(models.Model):
    TEXT = 'text'
    NUMBER = 'number'
    CHOICE = 'choice'
    MULTI_CHOICE = 'multi_choice'

    QUESTION_TYPE_CHOICES = [
        (TEXT, 'Text'),
        (NUMBER, 'number'),
        (CHOICE, 'single choice'),
        (MULTI_CHOICE, 'Multiple Choice'),
    ]
    
    goal = models.ForeignKey(Goal, on_delete=models.SET_NULL , null=True, related_name="questions")
    question = models.TextField(max_length=1000)
    question_type = models.CharField(max_length=20,
                                     choices=QUESTION_TYPE_CHOICES,
                                     default="text"
                                     )
    order = models.IntegerField(default=0)  # Question ordering
    is_required = models.BooleanField(default=True)
    help_text = models.CharField(max_length=500, blank=True)
    category = models.CharField(max_length=50, choices=[
        ('basic_info', 'Basic Information'),
        ('fitness_level', 'Fitness Level'),
        ('preferences', 'Preferences'),
        ('medical', 'Medical/Health'),
        ('goals', 'Goal Specifics'),
        ('diet', 'Diet Preferences'),
    ], default='basic_info')
    
    class Meta:
        ordering = ['order']
        
        
    def __str__(self):
        return self.question
    
    @property
    def is_single_choice(self):
        return self.question_type == self.CHOICE

    @property
    def is_multi_choice(self):
        return self.question_type == self.MULTI_CHOICE
    
class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    choice = models.CharField(max_length=255)
    value = models.CharField(max_length=100, blank=True)  # For mapping to system values
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
        
    def __str__(self):
        return self.choice
    
class Answer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    text_answer = models.TextField(blank=True, null=True)
    numeric_answer = models.DecimalField(max_digits=6, decimal_places=2 ,blank=True, null=True)
    choice_answer = models.ForeignKey(Choice, on_delete=models.SET_NULL, blank=True, null=True)
    multi_choice_answer = models.ManyToManyField(Choice, blank=True, related_name="multi_answers")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'question']
        
    def __str__(self):
        return f"{self.user} - {self.question}"
    
    
class UserGoal(models.Model):
    """User's selected goals with their questionnaire responses"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_goals')
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE)
    
    # Status tracking
    STATUS_CHOICES = [
        ('questionnaire', 'Completing Questionnaire'),
        ('processing', 'Processing Responses'),
        ('active', 'Active Plans Generated'),
        ('completed', 'Goal Completed'),
        ('paused', 'Paused'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='questionnaire')
    
    # Calculated fields from questionnaire
    fitness_level = models.CharField(max_length=20, choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ], blank=True)
    
    # User metrics (can be populated from questionnaire)
    current_weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    target_weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    
    # Preferences extracted from questionnaire
    workout_days_per_week = models.IntegerField(null=True, blank=True)
    preferred_workout_duration = models.IntegerField(null=True, blank=True)  # minutes
    daily_calorie_target = models.IntegerField(null=True, blank=True)
    
    # Timeline
    target_date = models.DateField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'goal']
    
    def __str__(self):
        return f"{self.user.username} - {self.goal.name}"
    
    def calculate_bmi(self):
        """Calculate BMI if weight and height are available"""
        if self.current_weight and self.height:
            height_m = float(self.height) / 100  # Convert cm to meters
            return float(self.current_weight) / (height_m ** 2)
        return None