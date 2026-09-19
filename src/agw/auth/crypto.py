"""Cryptographic utilities for encrypting tokens at rest."""

import base64
import os
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet


class TokenEncryption:
    """Manages symmetric Fernet encryption for OAuth refresh tokens."""

    def __init__(self, key: Optional[str] = None, key_file_path: str = "data/vault.key"):
        self.key_file = Path(key_file_path)
        if key:
            self._fernet = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
        else:
            loaded_key = self._get_or_create_key()
            self._fernet = Fernet(loaded_key)

    def _get_or_create_key(self) -> bytes:
        """Read key from file or generate a new one with restrictive permissions."""
        if self.key_file.is_file():
            key = self.key_file.read_bytes().strip()
            if key:
                return key

        # Generate new key
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        new_key = Fernet.generate_key()
        self.key_file.write_bytes(new_key)

        # Restrict permissions on POSIX systems
        try:
            if hasattr(os, "chmod"):
                os.chmod(self.key_file, 0o600)
        except Exception:
            pass

        return new_key

    def encrypt(self, plain_token: str) -> str:
        """Encrypt plaintext token to a URL-safe base64 string."""
        if not plain_token:
            return ""
        encrypted_bytes = self._fernet.encrypt(plain_token.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def decrypt(self, encrypted_token: str) -> str:
        """Decrypt encrypted token string back to plaintext."""
        if not encrypted_token:
            return ""
        decrypted_bytes = self._fernet.decrypt(encrypted_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
