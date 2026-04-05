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


class SuperAdminAccountDetail(EncryptedFieldsMixin, models.Model):
    CARD_DESIGN_GOLDEN = 'golden'
    CARD_DESIGN_PLATINUM = 'platinum'
    CARD_DESIGN_DIAMOND = 'diamond'
    CARD_DESIGN_CHOICES = (
        (CARD_DESIGN_GOLDEN, 'Golden'),
        (CARD_DESIGN_PLATINUM, 'Platinum'),
        (CARD_DESIGN_DIAMOND, 'Diamond'),
    )

    ENCRYPTED_FIELDS = (
        'account_holder_name',
        'bank_name',
        'account_number',
        'ifsc_code',
    )

    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='super_admin_account_details',
        null=True,
        blank=True,
    )
    # Legacy column kept in sync for databases that still require it.
    name = models.CharField(max_length=255, blank=True, default='', editable=False)
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
    card_design = models.CharField(
        max_length=32,
        choices=CARD_DESIGN_CHOICES,
        default=CARD_DESIGN_GOLDEN,
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', 'id']

    def save(self, *args, **kwargs):
        self.account_holder_name = (self.account_holder_name or '').strip()
        self.name = self.account_holder_name[:255]
        self.bank_name = (self.bank_name or '').strip()
        self.account_number = (self.account_number or '').strip()
        self.ifsc_code = (self.ifsc_code or '').strip().upper()
        self.card_design = (self.card_design or self.CARD_DESIGN_GOLDEN).strip().lower()
        originals = self._encrypt_encrypted_fields()
        try:
            super().save(*args, **kwargs)
        finally:
            for field_name, value in originals.items():
                setattr(self, field_name, value)

    def __str__(self):
        return f'{self.account_holder_name} - {self.bank_name}'
