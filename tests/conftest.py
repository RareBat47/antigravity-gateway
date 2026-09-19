"""Pytest fixtures for unit and integration testing."""

import os
import shutil
import tempfile
import pytest
from cryptography.fernet import Fernet

from agw.auth.crypto import TokenEncryption
from agw.auth.vault import CredentialVault
from agw.config import AppConfig
from agw.db.repository import DatabaseRepository
from tests.mock_upstream import MockCloudCodeClient


@pytest.fixture
def temp_dir():
    """Create isolated temporary directory for test storage."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def test_config(temp_dir):
    """Create isolated test configuration."""
    cfg = AppConfig()
    cfg.storage.database_path = os.path.join(temp_dir, "test_gateway.db")
    cfg.storage.vault_key_path = os.path.join(temp_dir, "test_vault.key")
    cfg.storage.quota_state_path = os.path.join(temp_dir, "test_quota.json")
    cfg.storage.status_report_path = os.path.join(temp_dir, "test_status.md")
    cfg.security.encryption_key = Fernet.generate_key().decode()
    cfg.security.gateway_api_key = "test-gateway-key"
    cfg.security.admin_api_key = "test-admin-key"
    return cfg


@pytest.fixture
async def test_repo(test_config):
    """Initialized SQLite repository fixture."""
    repo = DatabaseRepository(db_path=test_config.storage.database_path)
    await repo.init_db()
    return repo


@pytest.fixture
def test_vault(test_config):
    """Isolated credential vault fixture."""
    crypto = TokenEncryption(key=test_config.security.encryption_key)
    enc_path = os.path.join(os.path.dirname(test_config.storage.database_path), "test_vault.enc")
    return CredentialVault(vault_path=enc_path, crypto=crypto)


@pytest.fixture
def mock_client():
    """Mock CloudCodeClient fixture."""
    return MockCloudCodeClient()
