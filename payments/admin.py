from django.contrib import admin
from .models import ProfessorsPayments


@admin.register(ProfessorsPayments)
class ProfessorsPaymentsAdmin(admin.ModelAdmin):
    list_display = ('id', 'professor', 'institute', 'month_year', 'payment_date', 'payment_amount', 'payment_status')
    search_fields = ('professor__name', 'month_year', 'payment_status')
    list_filter = ('payment_status', 'institute')
