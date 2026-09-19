"""Tests for token encryption, decryption, and secure credential vault."""

import pytest
from agw.auth.crypto import TokenEncryption
from agw.auth.oauth import generate_pkce


def test_pkce_generation():
    verifier, challenge = generate_pkce()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert "=" not in challenge


def test_build_auth_url_formatting():
    from agw.auth.oauth import build_auth_url
    from agw.constants import DEFAULT_CLIENT_ID
    url = build_auth_url(
        client_id=DEFAULT_CLIENT_ID,
        redirect_uri="http://127.0.0.1:8999/auth/callback",
        state="test-state-123",
        code_challenge="test-challenge-xyz",
    )
    assert "client_id=" in url
    assert "client_id=client_id=" not in url
    assert "redirect_uri=redirect_uri=" not in url
    assert "response_type=code" in url
    assert "1071006060591" in url


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
