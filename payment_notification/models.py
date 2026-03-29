from django.core.validators import RegexValidator
from django.db import models

from institute_api.encryption import EncryptedFieldsMixin


account_number_validator = RegexValidator(
    regex=r'^\d{6,20}$',
    message='Account number must contain 6 to 20 digits.',
)

ifsc_validator = RegexValidator(
    regex=r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$',
    message='IFSC code must be in the format ABCD0123456.',
)

payment_month_validator = RegexValidator(
    regex=r'^\d{4}-\d{2}$',
    message='Payment month must be in YYYY-MM format.',
)


class PaymentNotification(EncryptedFieldsMixin, models.Model):
    ENCRYPTED_FIELDS = (
        'account_holder_name',
        'bank_name',
        'account_number',
        'ifsc_code',
        'final_amount',
        'payment_month',
        'payment_date',
        'approved_leaves',
    )

    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='payment_notifications',
    )
    professor = models.ForeignKey(
        'professors.Professor',
        on_delete=models.CASCADE,
        related_name='payment_notifications',
    )
    payment_month_key = models.CharField(
        max_length=7,
        validators=[payment_month_validator],
    )
    account_holder_name = models.CharField(max_length=1024)
    bank_name = models.CharField(max_length=1024)
    account_number = models.CharField(
        max_length=1024,
        validators=[account_number_validator],
    )
    ifsc_code = models.CharField(
        max_length=1024,
        validators=[ifsc_validator],
    )
    final_amount = models.CharField(max_length=1024)
    payment_month = models.CharField(max_length=1024)
    payment_date = models.CharField(max_length=1024)
    approved_leaves = models.CharField(max_length=1024)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['professor', 'payment_month_key'],
                name='uniq_payment_notification_prof_month',
            ),
        ]
        indexes = [
            models.Index(fields=['institute', 'payment_month_key'], name='pay_note_inst_month_idx'),
            models.Index(fields=['institute', 'professor'], name='pay_note_inst_prof_idx'),
        ]
        ordering = ['-payment_month_key', 'id']

    def save(self, *args, **kwargs):
        self.payment_month_key = self.payment_month_key.strip()
        self.account_holder_name = self.account_holder_name.strip()
        self.bank_name = self.bank_name.strip()
        self.account_number = self.account_number.strip()
        self.ifsc_code = self.ifsc_code.strip().upper()
        self.final_amount = str(self.final_amount).strip()
        self.payment_month = str(self.payment_month).strip()
        self.payment_date = str(self.payment_date).strip()
        self.approved_leaves = str(self.approved_leaves).strip()
        originals = self._encrypt_encrypted_fields()
        try:
            super().save(*args, **kwargs)
        finally:
            for field_name, value in originals.items():
                setattr(self, field_name, value)

    def __str__(self):
        return f'{self.professor.name} - {self.payment_month_key}'
