from django.db import models


class ProfessorsPayments(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='professors_payments',
        null=True, blank=True
    )
    professor = models.ForeignKey(
        'professors.Professor',
        on_delete=models.CASCADE,
        related_name='payments',
        null=True, blank=True
    )
    # YYYY-MM, used as the unique key for upsert (one record per professor per month)
    month_year = models.CharField(max_length=7, default="")  # e.g. "2025-02"
    payment_date = models.DateField(null=True, blank=True)
    payment_amount = models.IntegerField(default=0)
    payment_status = models.CharField(max_length=20, default="")

    class Meta:
        # Ensures only one payment record per professor per month
        unique_together = ('professor', 'month_year')
        indexes = [
            models.Index(fields=['institute', 'month_year'], name='pay_inst_month_idx'),
            models.Index(fields=['institute', 'professor'], name='pay_inst_prof_idx'),
        ]
