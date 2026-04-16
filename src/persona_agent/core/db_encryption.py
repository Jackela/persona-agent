"""Database column encryption using Fernet.

Provides transparent application-layer encryption for SQLite text columns
with full backward compatibility for existing plaintext databases.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class FernetColumnEncryptor:
    """Encrypt/decrypt individual database columns with Fernet.

    When no key is provided, operates in passthrough mode: plaintext
    is encoded to bytes on write and decoded back to str on read,
    preserving backward compatibility with unencrypted databases.
    """

    def __init__(self, key: str | None) -> None:
        """Initialize the encryptor.

        Args:
            key: Base64-encoded Fernet key, or None for passthrough mode.
        """
        if key:
            self._cipher: Fernet | None = Fernet(key.encode())
        else:
            self._cipher = None

    def encrypt(self, plaintext: str | None) -> bytes | None:
        """Encrypt a plaintext string.

        Args:
            plaintext: Value to encrypt.

        Returns:
            Encrypted bytes, encoded bytes in passthrough mode, or None.
        """
        if plaintext is None:
            return None
        if self._cipher is not None:
            return self._cipher.encrypt(plaintext.encode())
        return plaintext.encode()

    def decrypt(self, ciphertext: bytes | str | None) -> str | None:
        """Decrypt a ciphertext value.

        Handles legacy plaintext strings (str), encrypted bytes, and
        passthrough-encoded bytes. Returns the original string on
        decryption failure to preserve backward compatibility.

        Args:
            ciphertext: Value to decrypt.

        Returns:
            Decrypted string, original plaintext string, or None.
        """
        if ciphertext is None:
            return None
        if self._cipher is None:
            if isinstance(ciphertext, bytes):
                return ciphertext.decode()
            return ciphertext
        if isinstance(ciphertext, str):
            return ciphertext
        try:
            return self._cipher.decrypt(ciphertext).decode()
        except InvalidToken:
            return ciphertext.decode()
