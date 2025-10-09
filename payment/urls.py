from django.urls import path
from .views import (
    PaymentCreateView,
    PaymentVerifyView,
    PaymentListView,
    PaymentDetailView
)

urlpatterns = [
    path('create/', PaymentCreateView.as_view(), name='payment-create'),
    path('verify/', PaymentVerifyView.as_view(), name='payment-verify'),
    path('list/', PaymentListView.as_view(), name='payment-list'),
    path('<uuid:order_id>/', PaymentDetailView.as_view(), name='payment-detail'),
]