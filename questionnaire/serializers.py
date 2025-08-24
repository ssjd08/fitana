from rest_framework import serializers
from django.utils import timezone
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
    # Input fields
    choice_answer_id = serializers.IntegerField(write_only=True, required=False)
    multi_choice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    # Output nested serializers
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
        text_answer = attrs.get('text_answer')
        numeric_answer = attrs.get('numeric_answer')
        choice_answer_id = attrs.get('choice_answer_id')
        multi_choice_ids = attrs.get('multi_choice_ids', [])

        if not question:
            raise serializers.ValidationError("Question is required")

        # Validate based on question type
        if question.question_type == Question.TEXT:
            if not text_answer:
                raise serializers.ValidationError("Text answer is required for text questions")
        
        elif question.question_type == Question.NUMBER:
            if numeric_answer is None:
                raise serializers.ValidationError("Numeric answer is required for number questions")
        
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


class UserGoalSerializer(serializers.ModelSerializer):
    goal_name = serializers.CharField(source='goal.name', read_only=True)
    goal_description = serializers.CharField(source='goal.description', read_only=True)
    bmi = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = UserGoal
        fields = [
            'id', 
            'user', 
            'goal',
            'goal_name',
            'goal_description',
            'status',
            'fitness_level',
            'current_weight',
            'target_weight',
            'height',
            'age',
            'workout_days_per_week',
            'preferred_workout_duration',
            'daily_calorie_target',
            'target_date',
            'started_at',
            'completed_at',
            'is_active',
            'bmi',
            'progress_percentage'
        ]
        read_only_fields = [
            'user', 
            'started_at', 
            'goal_name', 
            'goal_description',
            'bmi',
            'progress_percentage'
        ]
    
    def get_bmi(self, obj):
        return obj.calculate_bmi()
    
    def get_progress_percentage(self, obj):
        """Calculate progress percentage based on weight goals"""
        if obj.current_weight and obj.target_weight:
            # This is a simple calculation - you might want more sophisticated logic
            if obj.goal.category in ['weight_loss']:
                if obj.current_weight <= obj.target_weight:
                    return 100.0
                # Calculate progress towards target
                start_weight = getattr(obj, 'start_weight', obj.current_weight)  # You might want to track this
                progress = (start_weight - obj.current_weight) / (start_weight - obj.target_weight) * 100
                return max(0, min(100, progress))
            elif obj.goal.category in ['weight_gain']:
                if obj.current_weight >= obj.target_weight:
                    return 100.0
                start_weight = getattr(obj, 'start_weight', obj.current_weight)
                progress = (obj.current_weight - start_weight) / (obj.target_weight - start_weight) * 100
                return max(0, min(100, progress))
        return 0.0
    
    def validate(self, attrs):
        # Validate weight goals
        current_weight = attrs.get('current_weight')
        target_weight = attrs.get('target_weight')
        
        if current_weight and target_weight:
            if current_weight == target_weight:
                raise serializers.ValidationError(
                    "Current weight and target weight cannot be the same"
                )
        
        # Validate age
        age = attrs.get('age')
        if age and (age < 13 or age > 100):
            raise serializers.ValidationError("Age must be between 13 and 100")
        
        # Validate workout days
        workout_days = attrs.get('workout_days_per_week')
        if workout_days and (workout_days < 1 or workout_days > 7):
            raise serializers.ValidationError("Workout days per week must be between 1 and 7")
        
        return attrs


class BulkAnswerSerializer(serializers.Serializer):
    """Serializer for bulk answer submission"""
    answers = serializers.ListField(
        child=AnswerSerializer(),
        min_length=1,
        help_text="List of answers to submit"
    )
    
    def validate_answers(self, value: list) -> list:
        """Validate that all answers belong to the same goal"""
        if not value:
            raise serializers.ValidationError("At least one answer is required")
        
        # Check for duplicate questions
        question_ids = [answer_data.get('question') for answer_data in value]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError("Duplicate questions found in answers")
        
        return value