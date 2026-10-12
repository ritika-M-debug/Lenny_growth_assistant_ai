from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "The Lenny Growth Assistant"
    assert data["status"] == "online"

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_health_db_check_success():
    with patch("app.api.health.check_db_connection") as mock_check:
        mock_check.return_value = (True, "PostgreSQL database is reachable and accepting connections.")
        response = client.get("/health/db")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

def test_health_db_check_failure():
    with patch("app.api.health.check_db_connection") as mock_check:
        mock_check.return_value = (False, "Could not establish connection to the PostgreSQL database.")
        response = client.get("/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["status"] == "unhealthy"
        assert data["detail"]["database"] == "disconnected"
