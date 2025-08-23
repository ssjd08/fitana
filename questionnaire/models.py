from django.db import models
from django.conf import settings


# Create your models here.
class Goal(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name
    
class Question(models.Model):
    TEXT = 'text'
    NUMBER = 'number'
    CHOISE = 'choise'
    MULTI_CHOISE = 'multi_choice'

    QUESTION_TYPE_CHOICES = [
        (TEXT, 'Text'),
        (NUMBER, 'number'),
        (CHOISE, 'single choise'),
        (MULTI_CHOISE, 'Multiple Choice'),
    ]
    
    goal = models.ForeignKey(Goal, on_delete=models.SET_NULL , null=True, related_name="questions")
    question = models.TextField(max_length=1000)
    question_type = models.CharField(max_length=20,
                                     choices=QUESTION_TYPE_CHOICES,
                                     default="text"
                                     )
    
    def __str__(self):
        return self.question
    
    @property
    def is_single_choice(self):
        return self.question_type == self.CHOISE

    @property
    def is_multi_choice(self):
        return self.question_type == self.MULTI_CHOISE
    
class Choise(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choises")
    choise = models.CharField(max_length=255)
    
    def __str__(self):
        return self.choise
    
class Answer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    text_answer = models.TextField(blank=True, null=True)
    numeric_answer = models.DecimalField(max_digits=6, decimal_places=2 ,blank=True, null=True)
    choice_answer = models.ForeignKey(Choise, on_delete=models.SET_NULL, blank=True, null=True)
    multi_choice_answer = models.ManyToManyField(Choise, blank=True, related_name="multi_answers")
    
    def __str__(self):
        return f"{self.user} - {self.question}"