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


class EmployeeAccountDetail(EncryptedFieldsMixin, models.Model):
    ENCRYPTED_FIELDS = (
        'account_holder_name',
        'bank_name',
        'account_number',
        'ifsc_code',
    )

    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='employee_account_details',
    )
    professor = models.OneToOneField(
        'professors.Professor',
        on_delete=models.CASCADE,
        related_name='account_detail',
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['institute', 'professor'], name='emp_acc_inst_prof_idx'),
        ]

    def save(self, *args, **kwargs):
        self.account_holder_name = self.account_holder_name.strip()
        self.bank_name = self.bank_name.strip()
        self.account_number = self.account_number.strip()
        self.ifsc_code = self.ifsc_code.strip().upper()
        originals = self._encrypt_encrypted_fields()
        try:
            super().save(*args, **kwargs)
        finally:
            for field_name, value in originals.items():
                setattr(self, field_name, value)

    def __str__(self):
        return f'{self.professor.name} - {self.bank_name}'