from django.urls import path
from .views import GoalListCreateView, GoalDetailView, QuestionListCreateView, QuestionDetailView

app_name = 'your_app_name'  # Replace with your actual app name

urlpatterns = [
    # Goal endpoints
    path('goals/', GoalListCreateView.as_view(), name='goal-list-create'),
    path('goals/<int:pk>/', GoalDetailView.as_view(), name='goal-detail'),
    
    # Question endpoints
    path('questions/', QuestionListCreateView.as_view(), name='question-list-create'),
    path('questions/<int:pk>/', QuestionDetailView.as_view(), name='question-detail'),
]