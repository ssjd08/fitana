from django.urls import path
from .views import *

urlpatterns = [
    path('register/', SendOTPView.as_view(), name='send-code'),
    path('login/', VerifyOTPView.as_view(), name='vefify-code'),
    path('me/', MeView.as_view(), name='me'),
]