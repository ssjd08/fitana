from rest_framework import serializers
from .models import Question, Choise, Goal

class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = ["id", "name", "description"]
      
        
class QuestionSerializer(serializers.ModelSerializer):
    goal = serializers.CharField(write_only=True, required=False)  # Make optional for partial updates
    goal_name = serializers.CharField(source='goal.name', read_only=True)
    choice_options = serializers.ListField(
        child=serializers.CharField(max_length=255),
        write_only=True,
        required=False
    )
    choices = serializers.StringRelatedField(source='choises', many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = ["id", "goal", "goal_name", "question", "question_type", "choice_options", "choices"]
    
    def validate(self, attrs):
        """Validate that choice questions have choice_options (only for full updates)"""
        # Get current instance for partial updates
        instance = getattr(self, 'instance', None)
        
        # Determine final question_type
        question_type = attrs.get('question_type')
        if instance and question_type is None:
            question_type = instance.question_type
            
        choice_options = attrs.get('choice_options')
        
        # Only validate choice_options if question_type is being set to 'choice'
        # and choice_options are explicitly provided or it's a create operation
        if question_type == 'choice':
            if not instance:  # Create operation
                if not choice_options:
                    raise serializers.ValidationError(
                        "choice_options are required when question_type is 'choice'"
                    )
            elif "choice_options" in getattr(self, "initial_data", {}):  # Update with choice_options provided
                if not choice_options:
                    raise serializers.ValidationError(
                        "choice_options cannot be empty when question_type is 'choice'"
                    )
        
        return attrs
    
    def _get_goal_from_name(self, goal_name):
        """Helper method to get goal instance from name"""
        try:
            return Goal.objects.get(name=goal_name)
        except Goal.DoesNotExist:
            raise serializers.ValidationError(f"Goal '{goal_name}' does not exist.")
    
    def _handle_choice_options(self, question, choice_options):
        """Helper method to handle choice options creation/update"""
        # Clear existing choices
        question.choises.all().delete()
        
        # Create new choices
        for option in choice_options:
            Choise.objects.create(question=question, choise=option.strip())
    
    def create(self, validated_data):
        goal_name = validated_data.pop('goal')
        choice_options = validated_data.pop('choice_options', [])
        
        goal = self._get_goal_from_name(goal_name)
        validated_data['goal'] = goal
        
        question = Question.objects.create(**validated_data)
        
        # Handle choice options
        if choice_options and validated_data.get('question_type') == 'choice':
            self._handle_choice_options(question, choice_options)
        
        return question
    
    def update(self, instance, validated_data):
        goal_name = validated_data.pop('goal', None)
        
        # Check if choice_options was explicitly provided in the request
        choice_options_provided = "choice_options" in getattr(self, "initial_data", {})
        choice_options = validated_data.pop('choice_options', [])
        
        # Handle goal update if provided
        if goal_name:
            goal = self._get_goal_from_name(goal_name)
            validated_data['goal'] = goal
        
        # Get the question type (either new or existing)
        new_question_type = validated_data.get('question_type', instance.question_type)
        
        # Update question fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Handle choice options only if:
        # 1. choice_options was explicitly provided in the request, OR
        # 2. question_type changed to/from 'choice'
        if choice_options_provided:
            if new_question_type == 'choice':
                self._handle_choice_options(instance, choice_options)
            else:
                # If question type is not choice but options provided, clear choices
                instance.choises.all().delete()
        elif 'question_type' in validated_data:
            # Question type changed, handle accordingly
            if new_question_type == 'choice':
                # Changed to choice but no options provided - keep existing
                pass
            else:
                # Changed from choice to non-choice - delete existing choices
                instance.choises.all().delete()
        
        return instance
    
    def to_representation(self, instance):
        """Customize the output representation"""
        representation = super().to_representation(instance)
        representation.pop('goal', None)
        representation.pop('choice_options', None)
        return representation
    

class QuestionWithChoicesSerializer(serializers.ModelSerializer):
    options = serializers.StringRelatedField(source='choises', many=True, read_only=True)
    
    class Meta:
        model = Question   
        fields = ["id", "question", "question_type", "options"] 


class GoalWithQuestionsSerializer(serializers.ModelSerializer):
    questions = QuestionWithChoicesSerializer(many=True, read_only=True)
    
    class Meta:
        model = Goal
        fields = ["id", "name", "questions"]