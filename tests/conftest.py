"""
Pytest configuration and fixtures for netkit-api tests
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path for imports
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

# Set test environment variables BEFORE importing app
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["API_KEYS"] = "test-api-key-1,test-api-key-2"
os.environ["RATE_LIMIT_GLOBAL"] = "1000"  # High limits for testing
os.environ["RATE_LIMIT_PER_IP"] = "500"
os.environ["RATE_LIMIT_PER_KEY"] = "500"
os.environ["OIDC_ENABLED"] = "false"  # Disable OIDC for tests

from api.api import app


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def api_key():
    """Test API key"""
    return "test-api-key-1"


@pytest.fixture
def auth_headers(api_key):
    """Authentication headers with API key"""
    return {"X-API-Key": api_key}


@pytest.fixture
def invalid_auth_headers():
    """Invalid authentication headers"""
    return {"X-API-Key": "invalid-key"}
