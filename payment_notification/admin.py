from django.contrib import admin

from .models import PaymentNotification


@admin.register(PaymentNotification)
class PaymentNotificationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'institute',
        'professor',
        'payment_month_key',
        'final_amount',
        'payment_date',
    )
    search_fields = (
        'institute__name',
        'professor__name',
        'payment_month_key',
        'account_holder_name',
        'bank_name',
        'account_number',
        'ifsc_code',
    )
    list_filter = ('institute', 'payment_month_key')
