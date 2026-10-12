import pytest
from unittest.mock import patch, MagicMock
from app.core.config import Settings
from app.db.init_db import wait_for_db, init_db


def test_compose_database_url_generation():
    """Verify that settings correctly construct connection string for Docker service host 'db'."""
    settings = Settings(
        POSTGRES_USER="postgres",
        POSTGRES_PASSWORD="secure_password",
        POSTGRES_SERVER="db",
        POSTGRES_PORT="5432",
        POSTGRES_DB="lenny_growth_db"
    )
    url = settings.sync_database_url
    assert "postgresql+psycopg2://postgres:secure_password@db:5432/lenny_growth_db" in url


def test_cors_origins_include_docker_frontend():
    """Ensure CORS origins allow both local dev ports and Docker frontend port."""
    settings = Settings(
        ALLOWED_ORIGINS="http://localhost:5173,http://localhost:80,http://127.0.0.1:5173"
    )
    assert "http://localhost:5173" in settings.cors_origins
    assert "http://localhost:80" in settings.cors_origins
    assert "http://127.0.0.1:5173" in settings.cors_origins


def test_wait_for_db_immediate_success():
    """Verify wait_for_db succeeds immediately when PostgreSQL is available."""
    with patch("app.db.init_db.check_db_connection", return_value=(True, "Connected")):
        assert wait_for_db(max_retries=3, delay=0.01) is True


def test_wait_for_db_retry_then_success():
    """Verify wait_for_db retries on initial failure and returns True once DB comes online."""
    attempts = [False, False, True]

    def mock_check():
        success = attempts.pop(0)
        return success, "Status message"

    with patch("app.db.init_db.check_db_connection", side_effect=mock_check):
        assert wait_for_db(max_retries=5, delay=0.01) is True


def test_wait_for_db_max_retries_exhausted():
    """Verify wait_for_db handles persistent connection failures gracefully without crashing."""
    with patch("app.db.init_db.check_db_connection", return_value=(False, "Connection refused")):
        assert wait_for_db(max_retries=2, delay=0.01) is False
