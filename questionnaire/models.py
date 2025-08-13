from django.db import models
from django.conf import settings


# Create your models here.
class Goal(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name
    
class Question(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.SET_NULL , null=True, related_name="questions")
    question = models.TextField(max_length=1000)
    question_type = models.CharField(max_length=10,
                                     choices=[
                                         ("text", "Text"),
                                         ("number", "Number"),
                                         ("choice", "Choice"),
                                         ],
                                     default="text"
                                     )
    
    def __str__(self):
        return self.question
    
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
    
    def __str__(self):
        return f"{self.user} - {self.question}"