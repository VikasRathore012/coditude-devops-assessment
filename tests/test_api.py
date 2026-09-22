import importlib.util
import pathlib
import sys
from unittest.mock import patch
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/backend'))

def test_backend_exists():
    assert (ROOT / 'apps/backend/main.py').exists(), 'Backend implementation is missing'

def test_health_and_readiness():
    from main import app
    client = TestClient(app)
    assert client.get('/api/health').json() == {'status': 'ok'}
    with patch('main.check_database', return_value=None):
        assert client.get('/api/ready').status_code == 200
    with patch('main.check_database', side_effect=RuntimeError('password=do-not-expose')):
        response = client.get('/api/ready')
        assert response.status_code == 503
        assert 'do-not-expose' not in response.text


def test_missing_secret_configuration_fails_closed(monkeypatch):
    import pytest
    from main import database_credentials
    database_credentials.cache_clear()
    monkeypatch.delenv('DB_SECRET_ARN', raising=False)
    monkeypatch.setenv('APP_ENV', 'prod')
    with pytest.raises(RuntimeError, match='required outside local'):
        database_credentials(1)


def test_local_credentials_require_explicit_local_mode(monkeypatch):
    from main import database_credentials
    database_credentials.cache_clear()
    monkeypatch.delenv('DB_SECRET_ARN', raising=False)
    monkeypatch.setenv('APP_ENV', 'local')
    monkeypatch.setenv('DB_USER', 'localuser')
    monkeypatch.setenv('DB_PASSWORD', 'localtest')
    assert database_credentials(2)['username'] == 'localuser'
    database_credentials.cache_clear()
