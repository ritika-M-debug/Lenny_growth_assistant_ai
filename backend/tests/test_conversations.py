import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_conversation():
    response = client.post("/api/conversations", json={"title": "Product Strategy Chat"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Product Strategy Chat"
    assert "id" in data
    assert "created_at" in data


def test_list_conversations():
    c1 = client.post("/api/conversations", json={"title": "First Conversation"}).json()
    c2 = client.post("/api/conversations", json={"title": "Second Conversation"}).json()

    response = client.get("/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == c2["id"]


def test_get_conversation_with_messages_chronological():
    c = client.post("/api/conversations", json={"title": "Messages Test"}).json()
    conv_id = c["id"]

    m1 = client.post(f"/api/conversations/{conv_id}/messages", json={"content": "What is product-market fit?"})
    assert m1.status_code == 201

    m2 = client.post(f"/api/conversations/{conv_id}/messages", json={"content": "How do I measure user activation?"})
    assert m2.status_code == 201

    detail = client.get(f"/api/conversations/{conv_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["id"] == conv_id
    messages = data["messages"]
    assert len(messages) == 4

    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is product-market fit?"
    assert messages[1]["role"] == "assistant"
    assert len(messages[1]["content"]) > 0


def test_send_and_persist_message():
    c = client.post("/api/conversations", json={"title": "New Conversation"}).json()
    conv_id = c["id"]

    res = client.post(f"/api/conversations/{conv_id}/messages", json={"content": "Tell me about growth loops"})
    assert res.status_code == 201
    data = res.json()
    assert data["role"] == "assistant"
    assert len(data["content"]) > 0


    detail = client.get(f"/api/conversations/{conv_id}").json()
    assert detail["title"] == "Tell me about growth loops"


def test_get_invalid_conversation_id():
    response = client.get("/api/conversations/non-existent-uuid-12345")
    assert response.status_code == 404
    data = response.json()
    assert "was not found" in data["detail"]


def test_delete_conversation():
    c = client.post("/api/conversations", json={"title": "To Delete"}).json()
    conv_id = c["id"]

    del_res = client.delete(f"/api/conversations/{conv_id}")
    assert del_res.status_code == 200

    get_res = client.get(f"/api/conversations/{conv_id}")
    assert get_res.status_code == 404
