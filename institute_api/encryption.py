from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet, InvalidToken


ENCRYPTED_VALUE_PREFIX = 'enc::'

@lru_cache(maxsize=1)
def get_fernet():
    configured_key = getattr(settings, 'DATA_ENCRYPTION_KEY', '') or ''
    if not configured_key:
        raise ImproperlyConfigured(
            'DATA_ENCRYPTION_KEY must be set to a valid Fernet key.'
        )

    try:
        return Fernet(configured_key.encode('utf-8'))
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            'DATA_ENCRYPTION_KEY must be a valid Fernet key.'
        ) from exc


def is_encrypted_value(value):
    return isinstance(value, str) and value.startswith(ENCRYPTED_VALUE_PREFIX)


def encrypt_value(value):
    if value in (None, ''):
        return value
    if is_encrypted_value(value):
        return value

    token = get_fernet().encrypt(str(value).encode('utf-8')).decode('utf-8')
    return f'{ENCRYPTED_VALUE_PREFIX}{token}'


def decrypt_value(value):
    if value in (None, ''):
        return value
    if not is_encrypted_value(value):
        return value

    token = value[len(ENCRYPTED_VALUE_PREFIX):]
    try:
        return get_fernet().decrypt(token.encode('utf-8')).decode('utf-8')
    except InvalidToken as exc:
        raise ImproperlyConfigured(
            'Unable to decrypt encrypted data. Check DATA_ENCRYPTION_KEY.'
        ) from exc


class EncryptedFieldsMixin:
    ENCRYPTED_FIELDS = ()

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._decrypt_encrypted_fields()
        return instance

    def _decrypt_encrypted_fields(self):
        for field_name in self.ENCRYPTED_FIELDS:
            setattr(self, field_name, decrypt_value(getattr(self, field_name, None)))

    def _encrypt_encrypted_fields(self):
        originals = {}
        for field_name in self.ENCRYPTED_FIELDS:
            originals[field_name] = getattr(self, field_name, None)
            setattr(self, field_name, encrypt_value(originals[field_name]))
        return originals
