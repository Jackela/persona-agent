"""Tests for db_encryption module."""

import pytest
from cryptography.fernet import Fernet

from persona_agent.core.db_encryption import FernetColumnEncryptor


class TestFernetColumnEncryptor:
    """Tests for FernetColumnEncryptor."""

    @pytest.fixture
    def valid_key(self) -> str:
        """Generate a valid Fernet key."""
        return Fernet.generate_key().decode()

    @pytest.fixture
    def another_key(self) -> str:
        """Generate a different valid Fernet key."""
        return Fernet.generate_key().decode()

    @pytest.fixture
    def encryptor(self, valid_key: str) -> FernetColumnEncryptor:
        """Create an encryptor with a valid key."""
        return FernetColumnEncryptor(valid_key)

    def test_encrypt_decrypt_round_trip(self, encryptor: FernetColumnEncryptor) -> None:
        """Test encrypt/decrypt round-trip with a valid key."""
        plaintext = "hello world"
        ciphertext = encryptor.encrypt(plaintext)

        assert isinstance(ciphertext, bytes)
        assert ciphertext != plaintext.encode()

        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_decrypt_unicode(self, encryptor: FernetColumnEncryptor) -> None:
        """Test round-trip with unicode characters."""
        plaintext = "Hello 世界 🌍"
        ciphertext = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_none_returns_none(self, encryptor: FernetColumnEncryptor) -> None:
        """Test encrypt(None) returns None."""
        assert encryptor.encrypt(None) is None

    def test_decrypt_none_returns_none(self, encryptor: FernetColumnEncryptor) -> None:
        """Test decrypt(None) returns None."""
        assert encryptor.decrypt(None) is None

    def test_passthrough_encrypt(self) -> None:
        """Test passthrough mode (no key): encrypt returns encoded bytes."""
        encryptor = FernetColumnEncryptor(None)
        plaintext = "hello"
        ciphertext = encryptor.encrypt(plaintext)
        assert ciphertext == b"hello"

    def test_passthrough_decrypt_bytes(self) -> None:
        """Test passthrough mode (no key): decrypt bytes returns original string."""
        encryptor = FernetColumnEncryptor(None)
        assert encryptor.decrypt(b"hello") == "hello"

    def test_passthrough_decrypt_str(self) -> None:
        """Test passthrough mode (no key): decrypt str returns original string."""
        encryptor = FernetColumnEncryptor(None)
        assert encryptor.decrypt("hello") == "hello"

    def test_passthrough_none(self) -> None:
        """Test passthrough mode (no key): None returns None."""
        encryptor = FernetColumnEncryptor(None)
        assert encryptor.encrypt(None) is None
        assert encryptor.decrypt(None) is None

    def test_backward_compat_plaintext_str_with_cipher(
        self, encryptor: FernetColumnEncryptor
    ) -> None:
        """Backward compat: decrypting a plaintext str returns it directly."""
        plaintext = "legacy plaintext"
        result = encryptor.decrypt(plaintext)
        assert result == plaintext

    def test_backward_compat_non_fernet_bytes_with_cipher(
        self, encryptor: FernetColumnEncryptor
    ) -> None:
        """Backward compat: decrypting non-Fernet bytes returns decoded string."""
        raw_bytes = b"legacy passthrough bytes"
        result = encryptor.decrypt(raw_bytes)
        assert result == "legacy passthrough bytes"

    def test_key_rotation_wrong_key_returns_raw(
        self, encryptor: FernetColumnEncryptor, another_key: str
    ) -> None:
        """Wrong key raises InvalidToken internally and falls back to raw decoded string."""
        plaintext = "sensitive data"
        ciphertext = encryptor.encrypt(plaintext)

        wrong_encryptor = FernetColumnEncryptor(another_key)
        result = wrong_encryptor.decrypt(ciphertext)
        assert result == ciphertext.decode()
