from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView
from django.db.models import QuerySet
from django.db import transaction
from rest_framework.request import Request
from typing import Any

from .serializers import (
    GoalSerializer, 
    GoalWithQuestionsSerializer, 
    QuestionSerializer, 
    AnswerSerializer, 
    UserGoalSerializer
)
from .models import Goal, Question, Answer, UserGoal


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


class AnswerListCreateView(ListCreateAPIView):
    """
    List user's answers or create/update answers for questions.
    """
    serializer_class = AnswerSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self) -> QuerySet[Answer]:# type: ignore
        # Handle anonymous users (for Swagger documentation generation)
        if not self.request.user.is_authenticated:
            return Answer.objects.none()
        return Answer.objects.filter(user=self.request.user).select_related(
            'question', 'choice_answer'
        ).prefetch_related('multi_choice_answer')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BulkAnswerCreateView(CreateAPIView):
    """
    Submit multiple answers at once for a questionnaire.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        answers_data = request.data.get("answers", [])
        
        if not answers_data:
            return Response(
                {"error": "answers field is required and must not be empty"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        saved_answers = []
        errors = []
        
        with transaction.atomic():
            for i, answer_data in enumerate(answers_data):
                # Add user to each answer
                answer_data["user"] = request.user.id
                
                serializer = AnswerSerializer(data=answer_data)
                if serializer.is_valid():
                    # Check if answer already exists and update it
                    existing_answer = Answer.objects.filter(
                        user=request.user,
                        question_id=answer_data.get('question')
                    ).first()
                    
                    if existing_answer:
                        # Update existing answer
                        update_serializer = AnswerSerializer(
                            existing_answer, 
                            data=answer_data, 
                            partial=True
                        )
                        if update_serializer.is_valid():
                            update_serializer.save()
                            saved_answers.append(update_serializer.data)
                        else:
                            errors.append({
                                "index": i,
                                "question_id": answer_data.get('question'),
                                "errors": update_serializer.errors
                            })
                    else:
                        # Create new answer
                        serializer.save(user=request.user)
                        saved_answers.append(serializer.data)
                else:
                    errors.append({
                        "index": i,
                        "question_id": answer_data.get('question'),
                        "errors": serializer.errors
                    })
        
        if errors:
            return Response({
                "detail": "Some answers had validation errors",
                "saved_answers": saved_answers,
                "errors": errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            "detail": f"Successfully saved {len(saved_answers)} answers",
            "answers": saved_answers
        }, status=status.HTTP_201_CREATED)


class UserGoalListCreateView(ListCreateAPIView):
    """
    List user's goals or create a new user goal.
    """
    serializer_class = UserGoalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self) -> QuerySet[UserGoal]:# type: ignore
        # Handle anonymous users (for Swagger documentation generation)
        if not self.request.user.is_authenticated:
            return UserGoal.objects.none()
        return UserGoal.objects.filter(
            user=self.request.user,
            is_active=True
        ).select_related('goal').order_by('-started_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserGoalDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a user goal.
    """
    serializer_class = UserGoalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self) -> QuerySet[UserGoal]: # type: ignore
        # Handle anonymous users (for Swagger documentation generation)
        if not self.request.user.is_authenticated:
            return UserGoal.objects.none()
        return UserGoal.objects.filter(user=self.request.user)
    
    def perform_update(self, serializer):
        # Auto-update completed_at when status changes to completed
        if serializer.validated_data.get('status') == 'completed':
            from django.utils import timezone
            serializer.save(completed_at=timezone.now())
        else:
            serializer.save()
    
    def destroy(self, request, *args, **kwargs):
        # Soft delete - just mark as inactive
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)