"""Fernet symmetric encryption for at-rest secrets (WordPress credentials)."""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

import app.core.config
from app.core.config import Settings

_cipher: Fernet | None = None
_settings: Settings | None = None


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = app.core.config.get_settings()
    return _settings


def get_cipher() -> Fernet:
    """Get the cached Fernet instance. Raises if ENCRYPTION_KEY not set."""
    global _cipher
    if _cipher is None:
        global _settings
        # Detect if get_settings was monkeypatched by checking if it's still
        # the original lru_cache-wrapped function. If not, reset to let the
        # monkeypatch take effect.
        current_get_settings = app.core.config.get_settings
        is_monkeypatched = not isinstance(current_get_settings, type(lru_cache(lambda: None)))
        if is_monkeypatched:
            _settings = None
        settings = _get_settings()
        if not settings.encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY not set in .env. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _cipher = Fernet(settings.encryption_key.encode())
    return _cipher


def reset_cipher() -> None:
    """Reset cached cipher (for testing or after settings change)."""
    global _cipher, _settings
    _cipher = None
    _settings = None


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext, return base64 string."""
    return get_cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt base64 ciphertext, return plaintext. Raises InvalidToken if tampered."""
    return get_cipher().decrypt(ciphertext.encode()).decode()
