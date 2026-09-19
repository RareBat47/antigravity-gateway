"""Secure credential vault for storing encrypted OAuth tokens."""

import json
import os
from pathlib import Path
from typing import Dict, Optional
from agw.auth.crypto import TokenEncryption


class CredentialVault:
    """Manages encrypted credential storage separate from metadata."""

    def __init__(self, vault_path: str = "data/vault.enc", crypto: Optional[TokenEncryption] = None):
        self.vault_path = Path(vault_path)
        self.crypto = crypto or TokenEncryption()
        self._cache: Dict[str, str] = {}  # account_id -> plain refresh_token
        self._load()

    def _load(self) -> None:
        """Load encrypted credentials from vault file into memory cache."""
        if not self.vault_path.is_file():
            return
        try:
            with open(self.vault_path, "r", encoding="utf-8") as f:
                encrypted_dict = json.load(f)
            for acc_id, enc_token in encrypted_dict.items():
                try:
                    plain = self.crypto.decrypt(enc_token)
                    self._cache[acc_id] = plain
                except Exception:
                    pass
        except Exception:
            pass

    def _save(self) -> None:
        """Encrypt and save all tokens to disk."""
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        encrypted_dict = {}
        for acc_id, plain in self._cache.items():
            if plain:
                encrypted_dict[acc_id] = self.crypto.encrypt(plain)
        with open(self.vault_path, "w", encoding="utf-8") as f:
            json.dump(encrypted_dict, f, indent=2)
        try:
            if hasattr(os, "chmod"):
                os.chmod(self.vault_path, 0o600)
        except Exception:
            pass

    def store_token(self, account_id: str, refresh_token: str) -> None:
        """Store a refresh token securely."""
        self._cache[account_id] = refresh_token
        self._save()

    def get_token(self, account_id: str) -> Optional[str]:
        """Retrieve the plaintext refresh token for an account."""
        return self._cache.get(account_id)

    def remove_token(self, account_id: str) -> None:
        """Remove a token for an account."""
        if account_id in self._cache:
            del self._cache[account_id]
            self._save()

    def has_token(self, account_id: str) -> bool:
        """Check if a refresh token exists for an account."""
        return bool(self._cache.get(account_id))
