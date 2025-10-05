from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
import json
import uuid

from .models import Question, Choice, Goal, Answer, UserGoal


class GoalSerializer(serializers.ModelSerializer):
    questions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Goal
        fields = ["id", "name", "description", "category", "questions_count", "is_active"]
        read_only_fields = ["questions_count"]
    
    def get_questions_count(self, obj):
        return obj.questions.count()


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "choice", "value", "order"]


class QuestionWithChoicesSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = [
            "id", 
            "question", 
            "question_type", 
            "order",
            "is_required",
            "help_text",
            "category",
            "choices"
        ]


class GoalWithQuestionsSerializer(serializers.ModelSerializer):
    questions = QuestionWithChoicesSerializer(many=True, read_only=True)
    
    class Meta:
        model = Goal
        fields = ["id", "name", "description", "category", "questions"]


class QuestionSerializer(serializers.ModelSerializer):
    goal = serializers.CharField(write_only=True, required=False)
    goal_name = serializers.CharField(source='goal.name', read_only=True)
    choice_options = serializers.ListField(
        child=serializers.CharField(max_length=255),
        write_only=True,
        required=False
    )
    choices = ChoiceSerializer(many=True, read_only=True)
    is_single_choice = serializers.SerializerMethodField()
    is_multi_choice = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            "id",
            "goal",
            "goal_name", 
            "question",
            "question_type",
            "order",
            "is_required",
            "help_text",
            "category",
            "choice_options",
            "choices",
            "is_single_choice",
            "is_multi_choice"
        ]

    def get_is_single_choice(self, obj):
        return obj.is_single_choice

    def get_is_multi_choice(self, obj):
        return obj.is_multi_choice

    def validate_choice_options(self, value: list) -> list:
        """Validate that choice options are provided for choice questions"""
        question_type = self.initial_data.get('question_type') # type: ignore
        if question_type in [Question.CHOICE, Question.MULTI_CHOICE]:
            if not value or len(value) < 2:
                raise serializers.ValidationError(
                    "At least 2 choice options are required for choice questions"
                )
        return value

    def _get_goal_from_name(self, goal_name: str) -> Goal:
        try:
            return Goal.objects.get(name=goal_name, is_active=True)
        except Goal.DoesNotExist:
            raise serializers.ValidationError(f"Active goal '{goal_name}' does not exist.")

    def _handle_choice_options(self, question: Question, choice_options: list) -> None:
        """Create/update choices for the question."""
        question.choices.all().delete() # type: ignore
        for i, option in enumerate(choice_options):
            Choice.objects.create(
                question=question, 
                choice=option.strip(),
                order=i
            )

    def create(self, validated_data):
        goal_name = validated_data.pop('goal', None)
        choice_options = validated_data.pop('choice_options', [])
        
        if goal_name:
            goal = self._get_goal_from_name(goal_name)
            validated_data['goal'] = goal

        question = Question.objects.create(**validated_data)

        if choice_options and question.question_type in [Question.CHOICE, Question.MULTI_CHOICE]:
            self._handle_choice_options(question, choice_options)

        return question

    def update(self, instance, validated_data):
        goal_name = validated_data.pop('goal', None)
        choice_options = validated_data.pop('choice_options', [])
        choice_options_provided = 'choice_options' in getattr(self, 'initial_data', {})

        if goal_name:
            validated_data['goal'] = self._get_goal_from_name(goal_name)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if choice_options_provided and instance.question_type in [Question.CHOICE, Question.MULTI_CHOICE]:
            self._handle_choice_options(instance, choice_options)

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('goal', None)
        representation.pop('choice_options', None)
        return representation


class AnswerSerializer(serializers.ModelSerializer):
    choice_answer_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    multi_choice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True
    )

    choice_answer = ChoiceSerializer(read_only=True)
    multi_choice_answer = ChoiceSerializer(many=True, read_only=True)
    question_text = serializers.CharField(source='question.question', read_only=True)

    class Meta:
        model = Answer
        fields = [
            "id",
            "user",
            "question",
            "question_text",
            "text_answer",
            "numeric_answer",
            "choice_answer",
            "multi_choice_answer",
            "choice_answer_id",
            "multi_choice_ids",
            "created_at",
            "updated_at"
        ]
        read_only_fields = ["choice_answer", "multi_choice_answer", "question_text", "created_at", "updated_at"]

    def validate(self, attrs):
        question = attrs.get('question')
        user = attrs.get('user')
        text_answer = attrs.get('text_answer')
        numeric_answer = attrs.get('numeric_answer')
        choice_answer_id = attrs.get('choice_answer_id')
        multi_choice_ids = attrs.get('multi_choice_ids', [])

        if not question:
            raise serializers.ValidationError("Question is required")
        if not user:
            raise serializers.ValidationError("User is required")

        # Check for existing answer
        if self.instance is None:  # Only for creation
            if Answer.objects.filter(user=user, question=question).exists():
                raise serializers.ValidationError(
                    "An answer for this user and question already exists."
                )

        # Validate based on question type
        if question.question_type == Question.TEXT:
            if not text_answer:
                raise serializers.ValidationError("Text answer is required for text questions")
            if choice_answer_id is not None:
                raise serializers.ValidationError("Choice answer should not be provided for text questions")
        
        elif question.question_type == Question.NUMBER:
            if numeric_answer is None:
                raise serializers.ValidationError("Numeric answer is required for number questions")
            if choice_answer_id is not None:
                raise serializers.ValidationError("Choice answer should not be provided for number questions")
        
        elif question.question_type == Question.CHOICE:
            if not choice_answer_id:
                raise serializers.ValidationError("Choice answer is required for choice questions")
        
        elif question.question_type == Question.MULTI_CHOICE:
            if not multi_choice_ids:
                raise serializers.ValidationError("Multi-choice answers are required for multi-choice questions")

        return attrs

    def create(self, validated_data):
        choice_id = validated_data.pop("choice_answer_id", None)
        multi_ids = validated_data.pop("multi_choice_ids", [])

        answer = Answer.objects.create(**validated_data)

        if choice_id:
            try:
                choice = Choice.objects.get(id=choice_id, question=answer.question)
                answer.choice_answer = choice
                answer.save()
            except Choice.DoesNotExist:
                raise serializers.ValidationError("Invalid choice for this question.")

        if multi_ids:
            choices = Choice.objects.filter(id__in=multi_ids, question=answer.question)
            if len(choices) != len(multi_ids):
                raise serializers.ValidationError("Some choices are invalid for this question.")
            answer.multi_choice_answer.set(choices)

        return answer

    def update(self, instance, validated_data):
        choice_id = validated_data.pop("choice_answer_id", None)
        multi_ids = validated_data.pop("multi_choice_ids", [])

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Handle choice answers
        if choice_id:
            try:
                choice = Choice.objects.get(id=choice_id, question=instance.question)
                instance.choice_answer = choice
                instance.save()
            except Choice.DoesNotExist:
                raise serializers.ValidationError("Invalid choice for this question.")
        elif choice_id == 0:  # Explicitly clear choice
            instance.choice_answer = None
            instance.save()

        # Handle multi-choice answers
        if multi_ids:
            choices = Choice.objects.filter(id__in=multi_ids, question=instance.question)
            if len(choices) != len(multi_ids):
                raise serializers.ValidationError("Some choices are invalid for this question.")
            instance.multi_choice_answer.set(choices)
        elif 'multi_choice_ids' in self.initial_data:  # type: ignore # Explicitly clear multi-choices
            instance.multi_choice_answer.clear()

        return instance


class AnonymousQuestionnaireSerializer(serializers.Serializer):
    """Serializer for anonymous questionnaire submission"""
    goal_id = serializers.IntegerField(required=True)
    phone = serializers.CharField(
        max_length=11,
        min_length=11,
        help_text="Phone number in format 09123456789"
    )
    answers = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of answers to submit"
    )
    
    # Optional user info that might be collected in questionnaire
    first_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    
    def validate_phone(self, value):
        """Validate phone number format"""
        import re
        # Normalize phone number
        phone = re.sub(r'\D', '', value)  # Remove non-digits
        if phone.startswith('98'):
            phone = '0' + phone[2:]
        elif phone.startswith('+98'):
            phone = '0' + phone[3:]
        
        pattern = r"^09\d{9}$"
        if not re.match(pattern, phone):
            raise serializers.ValidationError(
                "Phone number must be in format 09XXXXXXXXX"
            )
        return phone
    
    def validate_goal_id(self, value):
        """Validate that the goal exists"""
        from .models import Goal
        try:
            Goal.objects.get(id=value)
        except Goal.DoesNotExist:
            raise serializers.ValidationError(f"Goal with id {value} does not exist")
        return value
    
    def validate_answers(self, value):
        """Validate answers format"""
        if not value:
            raise serializers.ValidationError("At least one answer is required")
        
        # Check for duplicate questions
        question_ids = [answer.get("question") for answer in value]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError("Duplicate questions found in answers")
        
        # Validate each answer has required fields
        for i, answer in enumerate(value):
            if not answer.get("question"):
                raise serializers.ValidationError(f"Answer at index {i} is missing question field")
        
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        goal_id = attrs.get("goal_id")
        answers = attrs.get("answers", [])
        
        # Validate that all questions belong to the specified goal
        from .models import Question
        valid_question_ids = list(
            Question.objects.filter(goal_id=goal_id).values_list('id', flat=True)
        )
        
        question_ids = [answer.get("question") for answer in answers]
        invalid_questions = [qid for qid in question_ids if qid not in valid_question_ids]
        if invalid_questions:
            raise serializers.ValidationError(
                f"Questions {invalid_questions} do not belong to goal {goal_id}"
            )
        
        return attrs
    
    def save(self, *args, **kwargs):
        """Save questionnaire data to cache temporarily"""
        phone = self.validated_data['phone'] # type: ignore
        
        # Generate session ID for this submission
        session_id = str(uuid.uuid4())
        
        # Prepare data to cache
        cache_data = {
            'goal_id': self.validated_data['goal_id'], # type: ignore
            'phone': phone,
            'answers': self.validated_data['answers'], # type: ignore
            'first_name': self.validated_data.get('first_name', ''), # type: ignore
            'last_name': self.validated_data.get('last_name', ''), # type: ignore
            'email': self.validated_data.get('email', ''), # type: ignore
            'created_at': timezone.now().isoformat(),
            'session_id': session_id
        }
        
        # Cache for 1 hour
        cache_key = f"questionnaire_session_{session_id}"
        cache.set(cache_key, json.dumps(cache_data), timeout=3600)
        
        # Also cache by phone for easy retrieval
        phone_cache_key = f"questionnaire_phone_{phone}"
        cache.set(phone_cache_key, session_id, timeout=3600)
        
        return {
            'session_id': session_id,
            'phone': phone,
            'goal_id': self.validated_data['goal_id'], # type: ignore
            'answers_count': len(self.validated_data['answers']) # type: ignore
        }


class CompleteRegistrationSerializer(serializers.Serializer):
    """Serializer to complete registration after OTP verification"""
    session_id = serializers.UUIDField(required=True)
    
    def validate_session_id(self, value):
        """Validate that session exists in cache"""
        cache_key = f"questionnaire_session_{value}"
        cached_data = cache.get(cache_key)
        
        if not cached_data:
            raise serializers.ValidationError(
                "Session expired or not found. Please submit questionnaire again."
            )
        
        return value
    
    def complete_registration(self, user):
        """Complete user registration with cached questionnaire data"""
        from django.db import transaction
        from .models import Answer, UserGoal, Goal
        
        session_id = self.validated_data['session_id'] # type: ignore
        cache_key = f"questionnaire_session_{session_id}"
        cached_data_str = cache.get(cache_key)
        
        if not cached_data_str:
            raise serializers.ValidationError("Session data not found")
        
        cached_data = json.loads(cached_data_str)
        
        with transaction.atomic():
            # Create UserGoal
            goal = Goal.objects.get(id=cached_data['goal_id'])
            user_goal, created = UserGoal.objects.get_or_create(
                user=user,
                goal=goal,
                defaults={'created_at': timezone.now()}
            )
            
            # Save answers
            saved_answers = []
            for answer_data in cached_data['answers']:
                # Handle multi_choice_answer field name mapping if needed
                if "multi_choice_answer" in answer_data:
                    answer_data["multi_choice_ids"] = answer_data.pop("multi_choice_answer")
                
                answer_data["user"] = user.id
                
                from .serializers import AnswerSerializer
                serializer = AnswerSerializer(data=answer_data)
                if serializer.is_valid():
                    answer = serializer.save()
                    saved_answers.append(serializer.data)
            
            # Update user progress if available
            try:
                from plan.models import UserProgress
                progress, created = UserProgress.objects.get_or_create(
                    user=user,
                    defaults={'current_step': 'goal_selection'}
                )
                progress.selected_goal = user_goal
                progress.mark_step_completed('goal_selection')
            except ImportError:
                pass
            
            # Clean up cache
            cache.delete(cache_key)
            phone_cache_key = f"questionnaire_phone_{cached_data['phone']}"
            cache.delete(phone_cache_key)
            
            return {
                'user_goal_id': user_goal.id, # type: ignore
                'goal_name': goal.name,
                'answers_count': len(saved_answers),
                'answers': saved_answers
            }