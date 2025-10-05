# plan/urls.py
from django.urls import path
from .views import (
    UserProgressView, PlanGenerationView, RetryPlanGenerationView,
    UserPlanSummaryView, WorkoutPlanDetailView, DietPlanDetailView,
    UserWorkoutPlansView, UserDietPlansView, PlanVersionListView,
    ForceCompleteGenerationView, request_plan_modification,
    plan_statistics, cancel_plan_generation
)

app_name = 'plan'

urlpatterns = [
    # User Progress
    path('progress/', UserProgressView.as_view(), name='user-progress'),
    
    # Plan Generation
    path('generate/', PlanGenerationView.as_view(), name='generate-plan'),
    path('generate/<int:generation_id>/retry/', RetryPlanGenerationView.as_view(), name='retry-generation'),
    path('generate/<int:generation_id>/cancel/', cancel_plan_generation, name='cancel-generation'),
    
    # Current Plans
    path('my-plan/', UserPlanSummaryView.as_view(), name='user-plan-summary'),
    path('workout/', WorkoutPlanDetailView.as_view(), name='workout-detail'),
    path('diet/', DietPlanDetailView.as_view(), name='diet-detail'),
    
    # Plan History
    path('workouts/', UserWorkoutPlansView.as_view(), name='workout-list'),
    path('diets/', UserDietPlansView.as_view(), name='diet-list'),
    
    # Plan Versions
    path('versions/', PlanVersionListView.as_view(), name='plan-versions'),
    
    # Plan Modifications
    path('request-modification/', request_plan_modification, name='request-modification'),
    
    # Statistics & Info
    path('statistics/', plan_statistics, name='plan-statistics'),
    
    # Admin/Testing (remove in production)
    path('admin/force-complete/<int:generation_id>/', ForceCompleteGenerationView.as_view(), name='force-complete'),
]