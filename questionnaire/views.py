from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView
from django.db.models import QuerySet

from .serializers import GoalSerializer, GoalWithQuestionsSerializer, QuestionSerializer, AnswerSerializer
from .models import Goal, Question, Answer


class GoalListCreateView(ListCreateAPIView):
    """
    List all goals or create a new goal.
    Only admins can create goals.
    """
    serializer_class = GoalSerializer
    queryset = Goal.objects.all()
    
    def get_permissions(self):
        if self.request.method == "POST":  # Fixed: POST should be uppercase
            # Only admin can create goal
            return [IsAdminUser()]
        return [AllowAny()]


class GoalDetailView(RetrieveAPIView):
    """
    Retrieve a goal with all its associated questions and choices.
    """
    serializer_class = GoalWithQuestionsSerializer
    queryset = Goal.objects.prefetch_related("questions__choises").all()  # Fixed: prefetch choices too
    lookup_field = 'pk'  # Can be changed to 'name' if you want to lookup by goal name


class QuestionListCreateView(ListCreateAPIView):
    """
    List all questions or create a new question.
    """
    serializer_class = QuestionSerializer
    queryset = Question.objects.select_related('goal').all()  # Optimize query
    permission_classes = [AllowAny]  # Add explicit permissions
    
    
class QuestionDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve a question with all its choices.
    """
    serializer_class = QuestionSerializer
    queryset = Question.objects.prefetch_related('choises').all()
    lookup_field = 'pk'
    
    
class AnswerListCreateView(ListCreateAPIView):
    serializer_class = AnswerSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self)->QuerySet: # type: ignore
        return Answer.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        goal_id = request.data.get("goal")
        answer_data = request.data.get("answers")
        
        if not goal_id or not answer_data:
            return Response({"error": "goal and answers are required!"})
        
        saved_answers = []
        for ans in answer_data:
            ans["user"] = request.user.id
            ans["goal"] = goal_id
            serializer = AnswerSerializer(data=ans)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            saved_answers.append(serializer.data)
            
        return Response({"detail": "Answers saved", "answers": saved_answers}, status=status.HTTP_201_CREATED)