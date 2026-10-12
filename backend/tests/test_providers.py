import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import httpx

try:
    import anthropic
except ImportError:
    anthropic = None

from app.main import app
from app.agents.base import (
    BaseLLMProvider,
    ProviderConfigurationError,
    ProviderUnavailableError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ProviderTimeoutError,
    ProviderError,
)
from app.agents.rag_agent import RAGAgent, get_default_llm_provider
from app.agents.providers.ollama_provider import OllamaLLMProvider
from app.agents.providers.anthropic_provider import AnthropicLLMProvider
from app.agents.providers.claude_agent_provider import ClaudeAgentProvider
from app.agents.providers.mock_provider import MockLLMProvider
from app.knowledge_base.embeddings import DeterministicHashEmbeddingProvider
from app.knowledge_base.retrieval import RetrievalService
from app.knowledge_base.ingest import ingest_file
from tests.conftest import TestingSessionLocal


# -------------------------------------------------------------------------
# 1. Provider Selection from Environment
# -------------------------------------------------------------------------

def test_provider_selection_env_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    provider = get_default_llm_provider(allow_mock_override=False)
    assert isinstance(provider, OllamaLLMProvider)
    assert provider.provider_name == "ollama"


def test_provider_selection_env_anthropic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    provider = get_default_llm_provider(allow_mock_override=False)
    assert isinstance(provider, AnthropicLLMProvider)
    assert provider.provider_name == "anthropic"


def test_provider_selection_env_claude_agent_sdk(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude-agent-sdk")
    provider = get_default_llm_provider(allow_mock_override=False)
    assert isinstance(provider, ClaudeAgentProvider)
    assert provider.provider_name == "claude-agent-sdk"


def test_provider_selection_env_mock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    provider = get_default_llm_provider(allow_mock_override=False)
    assert isinstance(provider, MockLLMProvider)
    assert provider.provider_name == "mock"


def test_provider_selection_unsupported(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "invalid_provider_xyz")
    with pytest.raises(ProviderConfigurationError) as exc_info:
        get_default_llm_provider(allow_mock_override=False)
    assert "Unsupported LLM_PROVIDER" in str(exc_info.value)
    assert "ollama" in str(exc_info.value)
    assert "anthropic" in str(exc_info.value)


# -------------------------------------------------------------------------
# 2. Ollama Provider Reliability Tests (Hermetic / Mocked)
# -------------------------------------------------------------------------

def test_ollama_mocked_success():
    provider = OllamaLLMProvider(base_url="http://localhost:11434", model="llama3.2:3b", timeout=5.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {"role": "assistant", "content": "Retention is the foundation of growth."}
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.generate_chat_response([{"role": "user", "content": "Explain retention"}])
        assert res == "Retention is the foundation of growth."


def test_ollama_connection_failure():
    provider = OllamaLLMProvider(base_url="http://localhost:11434", model="llama3.2:3b", timeout=2.0)

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.generate_chat_response([{"role": "user", "content": "Hello"}])
        assert "ollama serve" in str(exc_info.value)
        assert "http://localhost:11434" in str(exc_info.value)


def test_ollama_missing_model():
    provider = OllamaLLMProvider(base_url="http://localhost:11434", model="nonexistent:latest", timeout=2.0)

    mock_req = httpx.Request("POST", "http://localhost:11434/api/chat")
    mock_resp = httpx.Response(404, request=mock_req)

    with patch("httpx.Client.post", side_effect=httpx.HTTPStatusError("Not found", request=mock_req, response=mock_resp)):
        with pytest.raises(ProviderModelNotFoundError) as exc_info:
            provider.generate_chat_response([{"role": "user", "content": "Hello"}])
        assert "ollama pull nonexistent:latest" in str(exc_info.value)


def test_ollama_timeout():
    provider = OllamaLLMProvider(base_url="http://localhost:11434", model="llama3.2:3b", timeout=2.0)

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(ProviderTimeoutError) as exc_info:
            provider.generate_chat_response([{"role": "user", "content": "Hello"}])
        assert "timed out" in str(exc_info.value)


def test_ollama_health_checks():
    provider = OllamaLLMProvider(base_url="http://localhost:11434", model="llama3.2:3b")

    # Case A: Reachable with model installed
    mock_ok = MagicMock()
    mock_ok.status_code = 200
    mock_ok.json.return_value = {"models": [{"name": "llama3.2:3b"}, {"name": "mistral:7b"}]}
    with patch("httpx.Client.get", return_value=mock_ok):
        health = provider.check_health()
        assert health["status"] == "available"
        assert health["reachable"] is True
        assert health["model_installed"] is True

    # Case B: Reachable but missing configured model
    mock_missing = MagicMock()
    mock_missing.status_code = 200
    mock_missing.json.return_value = {"models": [{"name": "mistral:7b"}]}
    with patch("httpx.Client.get", return_value=mock_missing):
        health = provider.check_health()
        assert health["status"] == "missing_model"
        assert health["reachable"] is True
        assert health["model_installed"] is False
        assert "ollama pull llama3.2:3b" in health["message"]

    # Case C: Unreachable
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Daemon down")):
        health = provider.check_health()
        assert health["status"] == "unavailable"
        assert health["reachable"] is False
        assert "ollama serve" in health["message"]


# -------------------------------------------------------------------------
# 3. Anthropic Provider Reliability Tests (Hermetic / Mocked)
# -------------------------------------------------------------------------

def test_anthropic_missing_api_key():
    provider = AnthropicLLMProvider(api_key="")
    with pytest.raises(ProviderConfigurationError) as exc_info:
        provider.generate_chat_response([{"role": "user", "content": "Hello"}])
    assert "ANTHROPIC_API_KEY is not configured" in str(exc_info.value)


def test_anthropic_placeholder_api_key():
    provider = AnthropicLLMProvider(api_key="your_anthropic_api_key_here")
    with pytest.raises(ProviderConfigurationError) as exc_info:
        provider.generate_chat_response([{"role": "user", "content": "Hello"}])
    assert "placeholder" in str(exc_info.value)


def test_anthropic_mocked_success():
    provider = AnthropicLLMProvider(api_key="sk-ant-test-mock-key-12345", model="claude-3-5-sonnet-20241022")

    mock_msg = MagicMock()
    mock_msg.text = "High activation velocity accelerates compounding loops."
    mock_response = MagicMock()
    mock_response.content = [mock_msg]

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response

        res = provider.generate_chat_response([{"role": "user", "content": "Explain activation"}])
        assert res == "High activation velocity accelerates compounding loops."


def test_anthropic_authentication_failure():
    provider = AnthropicLLMProvider(api_key="sk-ant-invalid-token", model="claude-3-5-sonnet-20241022")

    mock_req = MagicMock()
    auth_err = anthropic.AuthenticationError(
        message="Invalid API Key",
        response=MagicMock(status_code=401, headers={}),
        body={"error": {"message": "Invalid API Key"}}
    )

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = auth_err

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            provider.generate_chat_response([{"role": "user", "content": "Hello"}])
        assert "authentication failed" in str(exc_info.value).lower()


def test_anthropic_rate_limit_failure():
    provider = AnthropicLLMProvider(api_key="sk-ant-valid-token-12345", model="claude-3-5-sonnet-20241022")

    rate_err = anthropic.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429, headers={}),
        body={"error": {"message": "Rate limit exceeded"}}
    )

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = rate_err

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider.generate_chat_response([{"role": "user", "content": "Hello"}])
        assert "rate limit exceeded" in str(exc_info.value).lower()


def test_anthropic_timeout_failure():
    provider = AnthropicLLMProvider(api_key="sk-ant-valid-token-12345", timeout=5.0)

    timeout_err = anthropic.APITimeoutError(request=MagicMock())

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = timeout_err

        with pytest.raises(ProviderTimeoutError) as exc_info:
            provider.generate_chat_response([{"role": "user", "content": "Hello"}])
        assert "timed out" in str(exc_info.value).lower()


def test_anthropic_connection_failure():
    provider = AnthropicLLMProvider(api_key="sk-ant-valid-token-12345")

    conn_err = anthropic.APIConnectionError(request=MagicMock())

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = conn_err

        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.generate_chat_response([{"role": "user", "content": "Hello"}])
        assert "could not connect" in str(exc_info.value).lower()


def test_anthropic_health_masks_key():
    # When key is configured
    provider_configured = AnthropicLLMProvider(api_key="sk-ant-api03-abcdef1234567890xyz")
    health = provider_configured.check_health()
    assert health["status"] == "configured"
    assert health["configured"] is True
    # The full secret API key MUST NEVER be present in the output
    assert "sk-ant-api03-abcdef1234567890xyz" not in health["message"]
    assert health["key_preview"] == "sk-a...0xyz"

    # When key is missing
    provider_empty = AnthropicLLMProvider(api_key="")
    health_empty = provider_empty.check_health()
    assert health_empty["status"] == "unconfigured"
    assert health_empty["configured"] is False
    assert "ANTHROPIC_API_KEY is missing" in health_empty["message"]


# -------------------------------------------------------------------------
# 4. End-to-End Agent Integration Across Features
# -------------------------------------------------------------------------

def test_rag_citations_attached_with_mocked_provider():
    db = TestingSessionLocal()
    emb_provider = DeterministicHashEmbeddingProvider()

    # Create a custom provider to simulate any active model
    class CustomActiveProvider(BaseLLMProvider):
        @property
        def provider_name(self) -> str:
            return "anthropic"

        @property
        def model_name(self) -> str:
            return "claude-3-5-sonnet-20241022"

        def generate_chat_response(self, messages, system_prompt=None, temperature=0.7):
            return "According to [Source 1], product-market fit requires 40% retention threshold."

        def check_health(self):
            return {"status": "available", "provider": self.provider_name, "model": self.model_name}

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "pmf_doc.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("""---
title: PMF Playbook
type: podcast
author: Rahul Vohra
source_url: https://example.com/pmf-vohra
---
To measure product-market fit, ask users how they would feel if they could no longer use the product.
""")
        ingest_file(file_path, db, emb_provider, allowed_dirs=[tmp_dir])

        retriever = RetrievalService(db=db, embedding_provider=emb_provider)
        agent = RAGAgent(db=db, provider=CustomActiveProvider(), retrieval_service=retriever)
        resp = agent.run("How do I measure PMF?")

        assert resp.status == "success"
        assert resp.retrieved_count > 0
        assert len(resp.citations) > 0
        assert resp.citations[0].title == "PMF Playbook"
        assert resp.citations[0].author == "Rahul Vohra"
        assert resp.provider == "anthropic"
        assert resp.model == "claude-3-5-sonnet-20241022"


def test_ship_30_for_30_essay_with_configured_provider():
    db = TestingSessionLocal()
    retriever = RetrievalService(db=db, embedding_provider=DeterministicHashEmbeddingProvider())

    class EssayGeneratingProvider(BaseLLMProvider):
        @property
        def provider_name(self) -> str:
            return "ollama"

        @property
        def model_name(self) -> str:
            return "llama3.2:3b"

        def generate_chat_response(self, messages, system_prompt=None, temperature=0.7):
            return """# The Retention Flywheel
Most founders prioritize top-of-funnel acquisition over retention.
## Framework 1: The Core Loop
Solve customer onboarding in under 60 seconds.
## Conclusion
Compound growth through sticky user retention."""

        def check_health(self):
            return {"status": "available", "provider": self.provider_name, "model": self.model_name}

    agent = RAGAgent(db=db, provider=EssayGeneratingProvider(), retrieval_service=retriever)
    resp = agent.run("Write a Ship 30 for 30 essay on retention loops")

    assert resp.skill == "ship_30_for_30"
    assert resp.provider == "ollama"
    assert resp.extra_metadata["artifact_type"] == "markdown"
    assert "Word count:" in resp.content
    assert resp.extra_metadata["word_count"] > 0


def test_artifact_generation_with_configured_provider():
    db = TestingSessionLocal()
    retriever = RetrievalService(db=db, embedding_provider=DeterministicHashEmbeddingProvider())

    class HtmlGeneratingProvider(BaseLLMProvider):
        @property
        def provider_name(self) -> str:
            return "anthropic"

        @property
        def model_name(self) -> str:
            return "claude-3-5-sonnet-20241022"

        def generate_chat_response(self, messages, system_prompt=None, temperature=0.7):
            return """```html
<!DOCTYPE html>
<html>
<head><style>body { background: #000; color: #fff; }</style></head>
<body><div class="hero"><h1>Onboarding Funnel</h1></div><script>alert('xss');</script></body>
</html>
```"""

        def check_health(self):
            return {"status": "available", "provider": self.provider_name, "model": self.model_name}

    agent = RAGAgent(db=db, provider=HtmlGeneratingProvider(), retrieval_service=retriever)
    resp = agent.run("Create an HTML landing page for onboarding funnel")

    assert resp.skill == "artifact_generation"
    assert resp.extra_metadata["artifact_type"] == "html"
    # Ensure script tag was sanitized
    assert "<script" not in resp.extra_metadata["artifact_content"]
    assert "Onboarding Funnel" in resp.extra_metadata["artifact_content"]


# -------------------------------------------------------------------------
# 5. Reliability: Failure Handling Without Duplicate Messages or Artifacts
# -------------------------------------------------------------------------

def test_failure_handling_no_duplicate_messages_or_artifacts():
    with TestClient(app) as client:
        # Create a conversation
        c_res = client.post("/api/conversations", json={"title": "Reliability Test"})
        assert c_res.status_code == 201
        conv_id = c_res.json()["id"]

        # 1. Simulate failure during agent run (e.g. Ollama daemon offline)
        with patch("app.api.conversations.RAGAgent") as MockRAG:
            instance = MockRAG.return_value
            instance.provider.provider_name = "ollama"
            instance.provider.model_name = "llama3.2:3b"
            instance.run.side_effect = ProviderUnavailableError(
                "Could not connect to local Ollama service at http://localhost:11434. (ollama serve)"
            )

            msg_res = client.post(
                f"/api/conversations/{conv_id}/messages",
                json={"content": "What is activation?"}
            )
            assert msg_res.status_code == 201
            data = msg_res.json()
            assert data["role"] == "assistant"
            assert "unreachable" in data["content"] or "Ollama" in data["content"]
            assert data["metadata_json"]["status"] == "error"

        # Check conversation: exactly 1 user message and 1 assistant error message
        detail = client.get(f"/api/conversations/{conv_id}").json()
        assert len(detail["messages"]) == 2
        assert detail["messages"][0]["role"] == "user"
        assert detail["messages"][0]["content"] == "What is activation?"
        assert detail["messages"][1]["role"] == "assistant"
        assert detail["messages"][1]["metadata_json"]["status"] == "error"

        # Verify NO artifacts were created
        arts = client.get(f"/api/conversations/{conv_id}/artifacts").json()
        assert len(arts) == 0

        # 2. Now send a successful second message (retry or new query)
        msg_res2 = client.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": "What is activation? (retry)"}
        )
        assert msg_res2.status_code == 201

        # Check total messages: exactly 4 (2 user, 2 assistant) - no duplicate messages
        detail2 = client.get(f"/api/conversations/{conv_id}").json()
        assert len(detail2["messages"]) == 4
        assert [m["role"] for m in detail2["messages"]] == ["user", "assistant", "user", "assistant"]


# -------------------------------------------------------------------------
# 6. Diagnostic & Health Endpoints
# -------------------------------------------------------------------------

def test_health_endpoints_provider_resilience():
    with TestClient(app) as client:
        # /health endpoint should always succeed with basic app info
        h_res = client.get("/health")
        assert h_res.status_code == 200
        h_data = h_res.json()
        assert h_data["status"] == "healthy"
        assert "llm_provider" in h_data
        assert "model" in h_data

        # /health/llm diagnostic endpoint should never raise 500
        llm_res = client.get("/health/llm")
        assert llm_res.status_code == 200
        llm_data = llm_res.json()
        assert "status" in llm_data
        assert "provider" in llm_data
        assert "diagnostics" in llm_data
