from django.urls import path
from .views import (
    GoalListCreateView, GoalDetailView,
    QuestionListCreateView, QuestionDetailView,
    AnswerListCreateView, BulkAnswerCreateView,
    UserGoalListCreateView, UserGoalDetailView
)

urlpatterns = [
    path('goals/', GoalListCreateView.as_view(), name='goal-list-create'),
    path('goals/<int:pk>/', GoalDetailView.as_view(), name='goal-detail'),
    
    path('questions/', QuestionListCreateView.as_view(), name='question-list-create'),
    path('questions/<int:pk>/', QuestionDetailView.as_view(), name='question-detail'),
    
    path('answers/', AnswerListCreateView.as_view(), name='answer-list-create'),
    path('answers/bulk/', BulkAnswerCreateView.as_view(), name='bulk-answer-create'),
    
    path('user-goals/', UserGoalListCreateView.as_view(), name='user-goal-list-create'),
    path('user-goals/<int:pk>/', UserGoalDetailView.as_view(), name='user-goal-detail'),
]