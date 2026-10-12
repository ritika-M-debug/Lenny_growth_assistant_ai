import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.artifact import Artifact
from app.core.sanitizer import sanitize_html, validate_artifact_payload
from app.skills.artifact_generation import ArtifactGenerationSkill


# -------------------------------------------------------------------------
# 1. HTML Sanitizer & Security Tests
# -------------------------------------------------------------------------

def test_sanitizer_strips_script_tags():
    """Verifies that script tags and their inner JavaScript are stripped."""
    raw = "<div><h1>Welcome</h1><script>alert('pwned');</script><p>Safe content</p></div>"
    sanitized = sanitize_html(raw)
    assert "<script" not in sanitized.lower()
    assert "alert" not in sanitized
    assert "<h1>Welcome</h1>" in sanitized
    assert "<p>Safe content</p>" in sanitized


def test_sanitizer_strips_inline_event_handlers():
    """Verifies that malicious on* event handlers (onerror, onload, onclick) are stripped."""
    raw = '<img src="invalid.jpg" onerror="alert(1)" onload="fetch(\'/steal\')" /><button onclick="evil()">Click</button>'
    sanitized = sanitize_html(raw)
    assert "onerror" not in sanitized.lower()
    assert "onload" not in sanitized.lower()
    assert "onclick" not in sanitized.lower()
    assert "<img" in sanitized
    assert "<button" in sanitized


def test_sanitizer_strips_javascript_pseudo_protocols():
    """Verifies that javascript: URIs in links and src attributes are sanitized."""
    raw = '<a href="javascript:alert(document.cookie)">Click me</a>'
    sanitized = sanitize_html(raw)
    assert "javascript:" not in sanitized.lower()


def test_sanitizer_strips_nested_iframes_and_objects():
    """Verifies that embed, object, and nested iframe tags are removed."""
    raw = '<div><iframe src="https://evil.com"></iframe><embed src="file.swf" /><object data="test"></object></div>'
    sanitized = sanitize_html(raw)
    assert "<iframe" not in sanitized.lower()
    assert "<embed" not in sanitized.lower()
    assert "<object" not in sanitized.lower()


def test_sanitizer_preserves_legitimate_html_and_css():
    """Verifies that valid structural tags, CSS <style>, and classes are preserved."""
    raw = """
    <div class="hero-section">
      <style>
        .hero-section { background: #0f172a; color: white; padding: 2rem; }
        .hero-title { font-size: 2rem; font-weight: bold; }
      </style>
      <h1 class="hero-title">Lenny's Growth Framework</h1>
      <p>Master retention curves and PMF indicators.</p>
    </div>
    """
    sanitized = sanitize_html(raw)
    assert "hero-section" in sanitized
    assert "<style>" in sanitized
    assert "Lenny's Growth Framework" in sanitized
    assert "<p>Master retention curves and PMF indicators.</p>" in sanitized


def test_validate_artifact_payload():
    """Verifies payload validation rules for artifact type, title, and length."""
    # Valid markdown
    is_valid, err = validate_artifact_payload("PMF Playbook", "markdown", "# Playbook Content")
    assert is_valid is True
    assert err is None

    # Valid html
    is_valid, err = validate_artifact_payload("Waitlist Landing Page", "html", "<div>Landing</div>")
    assert is_valid is True
    assert err is None

    # Invalid type
    is_valid, err = validate_artifact_payload("Script", "python", "print('hello')")
    assert is_valid is False
    assert "Invalid artifact type" in err

    # Empty title
    is_valid, err = validate_artifact_payload("", "markdown", "Content")
    assert is_valid is False
    assert "title cannot be empty" in err.lower()

    # Empty content
    is_valid, err = validate_artifact_payload("Title", "markdown", "   ")
    assert is_valid is False
    assert "content cannot be empty" in err.lower()

    # Content exceeding length
    is_valid, err = validate_artifact_payload("Title", "markdown", "x" * 500_001)
    assert is_valid is False
    assert "exceeds" in err


# -------------------------------------------------------------------------
# 2. Artifact Skill Intent & Type Detection
# -------------------------------------------------------------------------

def test_artifact_skill_applicability():
    """Verifies that ArtifactGenerationSkill triggers on document/landing page requests."""
    skill = ArtifactGenerationSkill()

    # HTML triggers
    assert skill.is_applicable("Create an HTML landing page for a SaaS waitlist") is True
    assert skill.is_applicable("Build a landing page mockup with CSS") is True
    assert skill.is_applicable("Generate an HTML widget showing user metrics") is True

    # Markdown triggers
    assert skill.is_applicable("Create a markdown guide on retention loops") is True
    assert skill.is_applicable("Generate a growth report on product-market fit") is True
    assert skill.is_applicable("Draft a markdown document for user onboarding") is True
    assert skill.is_applicable("Create an artifact on B2B sales cycles") is True

    # Negative triggers (ordinary questions should not trigger skill)
    assert skill.is_applicable("What is product-market fit?") is False
    assert skill.is_applicable("How do I improve activation rates?") is False
    assert skill.is_applicable("Who is Lenny Rachitsky?") is False
    assert skill.is_applicable("") is False


def test_artifact_skill_type_classification():
    """Verifies classification between 'html' and 'markdown' types."""
    skill = ArtifactGenerationSkill()

    assert skill.determine_artifact_type("Generate an HTML landing page") == "html"
    assert skill.determine_artifact_type("Build a landing page for my product") == "html"
    assert skill.determine_artifact_type("Create a webpage mockup in HTML and CSS") == "html"

    assert skill.determine_artifact_type("Create a markdown guide on retention") == "markdown"
    assert skill.determine_artifact_type("Draft a growth report on activation") == "markdown"
    assert skill.determine_artifact_type("Generate a summary checklist") == "markdown"


# -------------------------------------------------------------------------
# 3. Artifact REST API CRUD Tests
# -------------------------------------------------------------------------

def test_create_artifact_via_api(client: TestClient):
    """Verifies POST /api/conversations/{id}/artifacts creates and persists artifact."""
    # 1. Create a conversation
    conv_res = client.post("/api/conversations", json={"title": "Test Artifact Conv"})
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # 2. Create artifact
    art_payload = {
        "title": "Onboarding Checklist",
        "type": "markdown",
        "content": "# Onboarding Checklist\n- Step 1\n- Step 2",
        "metadata_json": {"source": "manual_test"}
    }
    art_res = client.post(f"/api/conversations/{conv_id}/artifacts", json={
        "title": art_payload["title"],
        "type": art_payload["type"],
        "content": art_payload["content"],
        "metadata_json": art_payload["metadata_json"]
    })
    assert art_res.status_code == 201
    data = art_res.json()
    assert data["conversation_id"] == conv_id
    assert data["title"] == "Onboarding Checklist"
    assert data["type"] == "markdown"
    assert "- Step 1" in data["content"]
    assert "id" in data
    assert "created_at" in data


def test_create_html_artifact_sanitizes_content(client: TestClient):
    """Verifies that creating an HTML artifact automatically strips scripts before persisting."""
    conv_res = client.post("/api/conversations", json={"title": "HTML Conv"})
    conv_id = conv_res.json()["id"]

    art_res = client.post(f"/api/conversations/{conv_id}/artifacts", json={
        "title": "Unsafe Landing Page",
        "type": "html",
        "content": "<div><h1>Landing</h1><script>evil()</script><img src=x onerror=bad()></div>"
    })
    assert art_res.status_code == 201
    data = art_res.json()
    assert "<script" not in data["content"]
    assert "onerror" not in data["content"]
    assert "<h1>Landing</h1>" in data["content"]


def test_list_artifacts_for_conversation(client: TestClient):
    """Verifies GET /api/conversations/{id}/artifacts lists artifacts in descending chronological order."""
    conv_res = client.post("/api/conversations", json={"title": "List Artifacts Conv"})
    conv_id = conv_res.json()["id"]

    # Create 2 artifacts
    client.post(f"/api/conversations/{conv_id}/artifacts", json={
        "title": "Doc 1",
        "type": "markdown",
        "content": "# Doc 1"
    })
    client.post(f"/api/conversations/{conv_id}/artifacts", json={
        "title": "Doc 2",
        "type": "markdown",
        "content": "# Doc 2"
    })

    list_res = client.get(f"/api/conversations/{conv_id}/artifacts")
    assert list_res.status_code == 200
    artifacts = list_res.json()
    assert len(artifacts) == 2
    assert artifacts[0]["title"] == "Doc 2"  # Newest first
    assert artifacts[1]["title"] == "Doc 1"


def test_get_and_update_artifact_by_id(client: TestClient):
    """Verifies GET and PUT /api/artifacts/{id}."""
    conv_res = client.post("/api/conversations", json={"title": "Update Conv"})
    conv_id = conv_res.json()["id"]

    create_res = client.post(f"/api/conversations/{conv_id}/artifacts", json={
        "title": "Initial Title",
        "type": "markdown",
        "content": "# Initial Content"
    })
    art_id = create_res.json()["id"]

    # Get by ID
    get_res = client.get(f"/api/artifacts/{art_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Initial Title"

    # Update artifact
    update_res = client.put(f"/api/artifacts/{art_id}", json={
        "title": "Updated Title",
        "content": "# Updated Content\nAdded more details."
    })
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["title"] == "Updated Title"
    assert "Added more details" in updated_data["content"]


def test_delete_artifact_by_id(client: TestClient):
    """Verifies DELETE /api/artifacts/{id} removes the artifact."""
    conv_res = client.post("/api/conversations", json={"title": "Delete Conv"})
    conv_id = conv_res.json()["id"]

    create_res = client.post(f"/api/conversations/{conv_id}/artifacts", json={
        "title": "To Delete",
        "type": "markdown",
        "content": "# Delete Me"
    })
    art_id = create_res.json()["id"]

    # Delete
    del_res = client.delete(f"/api/artifacts/{art_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Confirm 404
    get_res = client.get(f"/api/artifacts/{art_id}")
    assert get_res.status_code == 404


def test_delete_conversation_cascades_to_artifacts(client: TestClient, db_session: Session):
    """Verifies that deleting a conversation cascades and deletes all associated artifacts."""
    conv_res = client.post("/api/conversations", json={"title": "Cascade Conv"})
    conv_id = conv_res.json()["id"]

    art_res = client.post(f"/api/conversations/{conv_id}/artifacts", json={
        "title": "Cascaded Doc",
        "type": "markdown",
        "content": "# Cascade Me"
    })
    art_id = art_res.json()["id"]

    # Delete the conversation
    del_conv = client.delete(f"/api/conversations/{conv_id}")
    assert del_conv.status_code == 200

    # Verify artifact is also deleted
    art_in_db = db_session.query(Artifact).filter(Artifact.id == art_id).first()
    assert art_in_db is None


# -------------------------------------------------------------------------
# 4. End-to-End Chat API Artifact Generation & Persistence
# -------------------------------------------------------------------------

def test_chat_message_generates_and_persists_html_artifact(client: TestClient):
    """Verifies sending an HTML landing page prompt triggers skill and persists an artifact record."""
    conv_res = client.post("/api/conversations", json={"title": "Chat HTML Test"})
    conv_id = conv_res.json()["id"]

    msg_res = client.post(f"/api/conversations/{conv_id}/messages", json={
        "content": "Create an HTML landing page for a SaaS waitlist"
    })
    assert msg_res.status_code == 201
    msg_data = msg_res.json()

    # Assistant message metadata must contain artifact reference
    assert msg_data["role"] == "assistant"
    metadata = msg_data.get("metadata_json", {})
    assert "artifact" in metadata or msg_data.get("artifact") is not None

    art_info = msg_data.get("artifact") or metadata.get("artifact")
    assert art_info["type"] == "html"
    assert "waitlist" in art_info["title"].lower() or "saas" in art_info["title"].lower()

    # Verify artifact was persisted in the database
    arts_res = client.get(f"/api/conversations/{conv_id}/artifacts")
    assert arts_res.status_code == 200
    arts = arts_res.json()
    assert len(arts) >= 1
    assert arts[0]["type"] == "html"


def test_chat_message_generates_and_persists_essay_artifact(client: TestClient):
    """Verifies sending a Ship 30 for 30 essay prompt persists a markdown artifact."""
    conv_res = client.post("/api/conversations", json={"title": "Chat Essay Test"})
    conv_id = conv_res.json()["id"]

    msg_res = client.post(f"/api/conversations/{conv_id}/messages", json={
        "content": "Write a Ship 30 for 30 essay on product-market fit"
    })
    assert msg_res.status_code == 201
    msg_data = msg_res.json()

    metadata = msg_data.get("metadata_json", {})
    art_info = msg_data.get("artifact") or metadata.get("artifact")
    assert art_info is not None
    assert art_info["type"] == "markdown"

    # Verify persisted in database
    arts_res = client.get(f"/api/conversations/{conv_id}/artifacts")
    assert arts_res.status_code == 200
    arts = arts_res.json()
    assert len(arts) >= 1
    assert arts[0]["type"] == "markdown"


def test_ordinary_chat_does_not_create_artifact(client: TestClient):
    """Verifies standard Q&A does not inadvertently produce or persist an artifact."""
    conv_res = client.post("/api/conversations", json={"title": "Standard QA Test"})
    conv_id = conv_res.json()["id"]

    msg_res = client.post(f"/api/conversations/{conv_id}/messages", json={
        "content": "What is the Sean Ellis test for PMF?"
    })
    assert msg_res.status_code == 201
    msg_data = msg_res.json()

    metadata = msg_data.get("metadata_json", {})
    assert "artifact" not in metadata
    assert msg_data.get("artifact") is None

    arts_res = client.get(f"/api/conversations/{conv_id}/artifacts")
    assert arts_res.status_code == 200
    assert len(arts_res.json()) == 0
