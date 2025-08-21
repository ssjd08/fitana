from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth import get_user_model
from .models import Goal, Question, Choise, Answer


User = get_user_model()

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
    
    is_multi_choice.boolean = True # type: ignore
    is_multi_choice.short_description = "Multiple Choice" # type: ignore


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Choise)
class ChoiseAdmin(admin.ModelAdmin):
    list_display = ('choise', 'question')
    search_fields = ('choise', 'question__question')


# Inline for showing answers in user detail page
# Inline for answers (read-only)
class AnswerInline(admin.TabularInline):
    model = Answer
    fields = ('question', 'text_answer', 'numeric_answer', 'choice_answer', 'get_multi_choices')
    readonly_fields = fields  # all fields read-only
    extra = 0
    can_delete = False

    def get_multi_choices(self, obj):
        return ", ".join([c.choise for c in obj.multi_choice_answer.all()])
    get_multi_choices.short_description = "Multi Choice Answers"

# Proxy model for admin view
class UserAnswer(User):
    class Meta:
        proxy = True
        verbose_name = "User Answers"
        verbose_name_plural = "Users Answers"

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('phone', 'full_name', 'all_answers')  # list page
    inlines = [AnswerInline]  # detail page shows answers only

    # Make user fields read-only
    readonly_fields = ('phone', 'first_name', 'last_name')

    # Only show these fields in detail page
    fields = ('phone', 'first_name', 'last_name')

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}" or "No Name"

    def all_answers(self, obj):
        answers = Answer.objects.filter(user=obj)
        answer_list = []
        for a in answers:
            if a.text_answer:
                ans = a.text_answer
            elif a.numeric_answer is not None:
                ans = str(a.numeric_answer)
            elif a.choice_answer:
                ans = a.choice_answer.choise
            elif a.multi_choice_answer.exists():
                ans = ", ".join([c.choise for c in a.multi_choice_answer.all()])
            else:
                ans = "No answer"
            answer_list.append(f"{a.question.question}: {ans}")
        return format_html("<br>".join(answer_list))# Inline for answers (read-only)
class AnswerInline(admin.TabularInline):
    model = Answer
    fields = ('question', 'text_answer', 'numeric_answer', 'choice_answer', 'get_multi_choices')
    readonly_fields = fields  # all fields read-only
    extra = 0
    can_delete = False

    def get_multi_choices(self, obj):
        return ", ".join([c.choise for c in obj.multi_choice_answer.all()])
    get_multi_choices.short_description = "Multi Choice Answers"

# Proxy model for admin view
class UserAnswer(User):
    class Meta:
        proxy = True
        verbose_name = "User Answers"
        verbose_name_plural = "Users Answers"

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('phone', 'full_name', 'all_answers')  # list page
    inlines = [AnswerInline]  # detail page shows answers only

    # Make user fields read-only
    readonly_fields = ('phone', 'first_name', 'last_name')

    # Only show these fields in detail page
    fields = ('phone', 'first_name', 'last_name')

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}" or "No Name"

    def all_answers(self, obj):
        answers = Answer.objects.filter(user=obj)
        answer_list = []
        for a in answers:
            if a.text_answer:
                ans = a.text_answer
            elif a.numeric_answer is not None:
                ans = str(a.numeric_answer)
            elif a.choice_answer:
                ans = a.choice_answer.choise
            elif a.multi_choice_answer.exists():
                ans = ", ".join([c.choise for c in a.multi_choice_answer.all()])
            else:
                ans = "No answer"
            answer_list.append(f"{a.question.question}: {ans}")
        return format_html("<br>".join(answer_list))