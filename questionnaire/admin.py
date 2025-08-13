from django.contrib import admin
from .models import Goal, Question, Choise, Answer

# Inline for choices
class ChoiseInline(admin.TabularInline):
    model = Choise
    extra = 2  # Number of empty rows to show
    # Optional: only show for choice/multi_choice questions
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(question__question_type__in=[Question.CHOISE, Question.MULTI_CHOISE])


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question', 'goal', 'question_type', 'is_single_choice', 'is_multi_choice')
    list_filter = ('goal', 'question_type')
    search_fields = ('question',)
    inlines = [ChoiseInline]

    def is_single_choice(self, obj):
        return obj.is_single_choice
    is_single_choice.boolean = True
    is_single_choice.short_description = "Single Choice"

    def is_multi_choice(self, obj):
        return obj.is_multi_choice
    is_multi_choice.boolean = True
    is_multi_choice.short_description = "Multiple Choice"


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Choise)
class ChoiseAdmin(admin.ModelAdmin):
    list_display = ('choise', 'question')
    search_fields = ('choise', 'question__question')


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'text_answer', 'numeric_answer')
    filter_horizontal = ('multi_choice_answer',)
