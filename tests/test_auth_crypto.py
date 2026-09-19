"""Tests for token encryption, decryption, and secure credential vault."""

import pytest
from agw.auth.crypto import TokenEncryption
from agw.auth.oauth import generate_pkce


def test_pkce_generation():
    verifier, challenge = generate_pkce()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert "=" not in challenge


def test_token_encryption_roundtrip(temp_dir):
    key_file = f"{temp_dir}/vault.key"
    enc = TokenEncryption(key_file_path=key_file)
    raw_token = "1//04mock_refresh_token_very_secret_xyz123"

    cipher = enc.encrypt(raw_token)
    assert cipher != raw_token
    assert "mock" not in cipher

    decrypted = enc.decrypt(cipher)
    assert decrypted == raw_token


def test_vault_persistence(test_vault):
    acc_id = "acc-test-1"
    token = "1//mock_refresh_secret"

    test_vault.store_token(acc_id, token)
    assert test_vault.has_token(acc_id) is True
    assert test_vault.get_token(acc_id) == token

    # Create new instance pointing to same file to test persistence
    new_vault = type(test_vault)(vault_path=str(test_vault.vault_path), crypto=test_vault.crypto)
    assert new_vault.has_token(acc_id) is True
    assert new_vault.get_token(acc_id) == token

    test_vault.remove_token(acc_id)
    assert test_vault.has_token(acc_id) is False
