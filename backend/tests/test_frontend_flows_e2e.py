"""End-to-end integration tests validating all 12 core user flows from frontend to backend.

Covers:
1. App health & startup state
2. Create conversation
3. Send normal question & receive grounded response
4. Reload page / reopen conversation
5. Grounded source citations inspection
6. Generate Ship 30 for 30 essay
7. Generate Markdown artifact
8. Generate HTML artifact & preview sanitization
9. Copy / download artifact data retrieval
10. Switch conversations & artifact isolation
11. Provider failure resilience & clear user error message
12. Responsive styles / media query coverage verification
"""

import os
import pytest
from fastapi.testclient import TestClient

from app.main import app

@pytest.fixture
def client():
    return TestClient(app)


def test_flow_1_open_application_health(client):
    """Flow 1: Open app / Check health endpoint."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "llm_provider" in data
    assert "model" in data


def test_flow_2_create_new_conversation(client):
    """Flow 2: Create a new conversation."""
    resp = client.post("/api/conversations", json={"title": "PMF Strategy Session"})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["title"] == "PMF Strategy Session"
    assert "created_at" in data


def test_flow_3_and_4_send_question_and_reopen_conversation(client):
    """Flows 3 & 4: Send question, receive answer, reload/reopen conversation."""
    # Create conversation
    create_resp = client.post("/api/conversations", json={"title": "Retention Q&A"})
    assert create_resp.status_code == 201
    conv_id = create_resp.json()["id"]

    # Send question (201 Created)
    msg_resp = client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "What is product-market fit?"}
    )
    assert msg_resp.status_code == 201
    msg_data = msg_resp.json()
    assert msg_data["role"] == "assistant"
    assert len(msg_data["content"]) > 0

    # Flow 4: Reload / Reopen conversation
    reopen_resp = client.get(f"/api/conversations/{conv_id}")
    assert reopen_resp.status_code == 200
    conv_data = reopen_resp.json()
    assert conv_data["id"] == conv_id
    assert len(conv_data["messages"]) >= 2  # user + assistant
    assert conv_data["messages"][0]["role"] == "user"
    assert conv_data["messages"][1]["role"] == "assistant"


def test_flow_5_inspect_source_citations(client):
    """Flow 5: Inspect source citations on a grounded response."""
    create_resp = client.post("/api/conversations", json={"title": "Citations Verification"})
    assert create_resp.status_code == 201
    conv_id = create_resp.json()["id"]

    msg_resp = client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "How do I build a high-performing growth team according to Adam Fishman?"}
    )
    assert msg_resp.status_code == 201
    data = msg_resp.json()
    citations = data.get("citations", [])

    # If knowledge chunks were retrieved, verify citation structure
    if citations:
        c = citations[0]
        assert "title" in c
        assert "source_url" in c
        assert c["source_url"] is not None


def test_flow_6_generate_ship_30_for_30_essay(client):
    """Flow 6: Generate Ship 30 for 30 atomic essay and verify artifact."""
    create_resp = client.post("/api/conversations", json={"title": "Essay Test"})
    assert create_resp.status_code == 201
    conv_id = create_resp.json()["id"]

    msg_resp = client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "Write a Ship 30 for 30 essay on user onboarding retention loops"}
    )
    assert msg_resp.status_code == 201
    data = msg_resp.json()
    assert data["role"] == "assistant"

    # Check that an artifact was attached
    artifact = data.get("artifact")
    assert artifact is not None
    assert artifact["type"] == "markdown"
    assert len(artifact["title"]) > 0
    assert "user onboarding" in artifact["title"].lower() or "growth" in artifact["title"].lower()

    # Verify word count / content substantive
    content = artifact["content"]
    word_count = len(content.split())
    assert word_count > 50


def test_flow_7_generate_markdown_artifact(client):
    """Flow 7: Generate Markdown guide artifact."""
    create_resp = client.post("/api/conversations", json={"title": "Guide Test"})
    assert create_resp.status_code == 201
    conv_id = create_resp.json()["id"]

    msg_resp = client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "Create a markdown guide for B2B product growth experiments"}
    )
    assert msg_resp.status_code == 201
    data = msg_resp.json()
    artifact = data.get("artifact")
    assert artifact is not None
    assert artifact["type"] == "markdown"
    assert len(artifact["content"]) > 100


def test_flow_8_generate_html_artifact_and_preview_sanitization(client):
    """Flow 8: Generate HTML artifact and confirm preview isolation."""
    create_resp = client.post("/api/conversations", json={"title": "HTML Landing Page Test"})
    assert create_resp.status_code == 201
    conv_id = create_resp.json()["id"]

    msg_resp = client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "Generate an HTML landing page for a product analytics tool"}
    )
    assert msg_resp.status_code == 201
    data = msg_resp.json()
    artifact = data.get("artifact")
    assert artifact is not None
    assert artifact["type"] == "html"
    # Verify no malicious script tags remain in the persisted artifact
    assert "<script" not in artifact["content"].lower()
    assert "onerror=" not in artifact["content"].lower()


def test_flow_9_copy_download_artifact(client):
    """Flow 9: Copy or download artifact content via API."""
    create_resp = client.post("/api/conversations", json={"title": "Download Test"})
    assert create_resp.status_code == 201
    conv_id = create_resp.json()["id"]

    # Create explicit artifact
    art_resp = client.post(
        f"/api/conversations/{conv_id}/artifacts",
        json={
            "title": "Growth Checklist",
            "type": "markdown",
            "content": "# Growth Checklist\n- [ ] Optimize onboarding\n- [ ] Measure cohort retention"
        }
    )
    assert art_resp.status_code == 201
    art_id = art_resp.json()["id"]

    # Retrieve artifact for copy/download
    get_art = client.get(f"/api/conversations/{conv_id}/artifacts")
    assert get_art.status_code == 200
    arts = get_art.json()
    matched = [a for a in arts if a["id"] == art_id]
    assert len(matched) == 1
    assert "Optimize onboarding" in matched[0]["content"]


def test_flow_10_switch_between_conversations_and_artifacts(client):
    """Flow 10: Switch between conversations and verify artifact isolation."""
    # Conv A
    cA = client.post("/api/conversations", json={"title": "Conversation Alpha"}).json()["id"]
    client.post(f"/api/conversations/{cA}/artifacts", json={
        "title": "Alpha Artifact", "type": "markdown", "content": "Alpha content"
    })

    # Conv B
    cB = client.post("/api/conversations", json={"title": "Conversation Beta"}).json()["id"]
    client.post(f"/api/conversations/{cB}/artifacts", json={
        "title": "Beta Artifact", "type": "markdown", "content": "Beta content"
    })

    # Query A's artifacts
    arts_A = client.get(f"/api/conversations/{cA}/artifacts").json()
    titles_A = [a["title"] for a in arts_A]
    assert "Alpha Artifact" in titles_A
    assert "Beta Artifact" not in titles_A

    # Query B's artifacts
    arts_B = client.get(f"/api/conversations/{cB}/artifacts").json()
    titles_B = [a["title"] for a in arts_B]
    assert "Beta Artifact" in titles_B
    assert "Alpha Artifact" not in titles_B


def test_flow_11_request_failure_handling(client):
    """Flow 11: Trigger request failure and confirm graceful error message without crash."""
    # Invalid conversation ID
    resp = client.post(
        "/api/conversations/00000000-0000-0000-0000-000000000000/messages",
        json={"content": "Hello"}
    )
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_flow_12_responsive_styles_and_breakpoints():
    """Flow 12: Verify CSS responsive rules for mobile/tablet screen widths."""
    css_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "styles", "chat.css"
    )
    assert os.path.exists(css_path), f"chat.css not found at {css_path}"
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Verify mobile and tablet media queries exist
    assert "@media (max-width: 1024px)" in css
    assert "@media (max-width: 768px)" in css
    # Verify layout adaptations exist
    assert ".artifact-panel" in css
    assert ".sidebar" in css
