from rest_framework import serializers
from .models import Question, Choice, Goal, Answer, UserGoal


class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = ["id", "name", "description"]


class QuestionSerializer(serializers.ModelSerializer):
    goal = serializers.CharField(write_only=True, required=False)
    goal_name = serializers.CharField(source='goal.name', read_only=True)
    choice_options = serializers.ListField(
        child=serializers.CharField(max_length=255),
        write_only=True,
        required=False
    )
    choices = serializers.StringRelatedField(many=True, read_only=True)
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
            "choice_options",
            "choices",
            "is_single_choice",
            "is_multi_choice"
        ]

    def get_is_single_choice(self, obj):
        return obj.is_single_choice

    def get_is_multi_choice(self, obj):
        return obj.is_multi_choice

    def _get_goal_from_name(self, goal_name):
        try:
            return Goal.objects.get(name=goal_name)
        except Goal.DoesNotExist:
            raise serializers.ValidationError(f"Goal '{goal_name}' does not exist.")

    def _handle_choice_options(self, question, choice_options):
        """Create/update choices for the question."""
        question.choices.all().delete()
        for option in choice_options:
            Choice.objects.create(question=question, choice=option.strip())

    def create(self, validated_data):
        goal_name = validated_data.pop('goal')
        choice_options = validated_data.pop('choice_options', [])
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


class QuestionWithChoicesSerializer(serializers.ModelSerializer):
    options = serializers.StringRelatedField(source='choices', many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["id", "question", "question_type", "options"]


class GoalWithQuestionsSerializer(serializers.ModelSerializer):
    questions = QuestionWithChoicesSerializer(many=True, read_only=True)

    class Meta:
        model = Goal
        fields = ["id", "name", "questions"]


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "question", "choice"]


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

    class Meta:
        model = Answer
        fields = [
            "id",
            "user",
            "question",
            "text_answer",
            "numeric_answer",
            "choice_answer",
            "multi_choice_answer",
            "choice_answer_id",
            "multi_choice_ids",
        ]
        read_only_fields = ["choice_answer", "multi_choice_answer"]

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
            answer.multi_choice_answer.set(choices)

        return answer


class UserGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserGoal
        fields = ['id', 'user', 'goal', 'is_completed']
        read_only_fields = ['user', 'is_completed']