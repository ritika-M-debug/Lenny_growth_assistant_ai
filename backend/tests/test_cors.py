from fastapi.testclient import TestClient
from app.main import app
from app.core.config import Settings

client = TestClient(app)


def test_cors_vercel_production_origin_allowed():
    """Verify that GET /health from the deployed Vercel frontend receives Access-Control-Allow-Origin."""
    response = client.get(
        "/health",
        headers={"Origin": "https://lenny-growth-assistant-ai.vercel.app"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://lenny-growth-assistant-ai.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_options_request_allowed():
    """Verify that OPTIONS preflight request from Vercel receives appropriate CORS headers."""
    response = client.options(
        "/api/conversations",
        headers={
            "Origin": "https://lenny-growth-assistant-ai.vercel.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://lenny-growth-assistant-ai.vercel.app"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_localhost_development_origin_allowed():
    """Verify that requests from local development origin (http://localhost:5173) are allowed."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_trailing_slash_and_whitespace_sanitization():
    """Verify that ALLOWED_ORIGINS with whitespace and trailing slashes are cleanly sanitized."""
    test_settings = Settings(
        ALLOWED_ORIGINS=" https://lenny-growth-assistant-ai.vercel.app/ , http://localhost:5173/ "
    )
    assert "https://lenny-growth-assistant-ai.vercel.app" in test_settings.cors_origins
    assert "http://localhost:5173" in test_settings.cors_origins
    # Ensure trailing slashes are absent
    assert not any(origin.endswith("/") for origin in test_settings.cors_origins)


def test_cors_unauthorized_origin_blocked():
    """Verify that an unauthorized third-party origin does not receive Access-Control-Allow-Origin."""
    response = client.get(
        "/health",
        headers={"Origin": "https://unauthorized-attacker-site.com"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None
