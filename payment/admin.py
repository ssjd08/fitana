from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'gateway', 'created_at')
    list_filter = ('status', 'gateway', 'created_at')
    search_fields = ('user__phone', 'order_id', 'ref_id', 'tracking_code')
    readonly_fields = ('order_id', 'created_at', 'updated_at', 'gateway_response')
