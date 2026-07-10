"""Tests for Fernet encryption helper."""
import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.domain.security.encryption import decrypt, encrypt, get_cipher


@pytest.fixture
def key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def settings_with_key(key: str) -> Settings:
    return Settings(encryption_key=key)


def test_cipher_is_cached(settings_with_key: Settings, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings_with_key)
    from app.domain.security import encryption
    encryption._cipher = None  # reset cache
    c1 = get_cipher()
    c2 = get_cipher()
    assert c1 is c2


def test_encrypt_decrypt_roundtrip(settings_with_key: Settings) -> None:
    from app.domain.security import encryption
    encryption._cipher = None
    plain = "my-secret-app-password"
    cipher_text = encrypt(plain)
    assert cipher_text != plain
    assert decrypt(cipher_text) == plain


def test_decrypt_with_wrong_key_raises(settings_with_key: Settings) -> None:
    from app.domain.security import encryption
    encryption._cipher = None
    cipher_text = encrypt("hello")
    # Switch to a different key
    other = Settings(encryption_key=Fernet.generate_key().decode())
    encryption._cipher = None
    from app.domain.security import encryption as enc
    enc._settings = other
    with pytest.raises(InvalidToken):
        decrypt(cipher_text)


def test_get_cipher_without_key_raises(monkeypatch) -> None:
    from app.domain.security import encryption
    encryption._cipher = None
    monkeypatch.setattr("app.core.config.get_settings", lambda: Settings(encryption_key=""))
    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        get_cipher()
