from django.urls import path
from .views import (
    PaymentCreateView,
    PaymentListView,
    PaymentDetailView,
    PaymentVerifyView,
    PaymentRefundView
)

app_name = 'payment'

urlpatterns = [
    path('create/', PaymentCreateView.as_view(), name='payment-create'),
    path('list/', PaymentListView.as_view(), name='payment-list'),
    path('detail/<uuid:order_id>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('verify/<str:ref_id>/', PaymentVerifyView.as_view(), name='payment-verify'),
    path('refund/<uuid:order_id>/', PaymentRefundView.as_view(), name='payment-refund'),
]