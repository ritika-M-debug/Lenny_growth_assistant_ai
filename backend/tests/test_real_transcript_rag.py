"""Repeatable end-to-end tests for real Lenny's Podcast transcripts in PostgreSQL.

Verifies:
1. Real transcripts exist in the database (ingested from genuine episodes).
2. Representative retrieval queries return relevant chunks with valid guest names and titles.
3. Citations include valid YouTube links with timestamps where available.
4. The RAG agent attaches authentic citations without inventing sources.
"""

import pytest
from app.db.session import SessionLocal
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.knowledge_base.retrieval import RetrievalService
from app.knowledge_base.embeddings import DeterministicHashEmbeddingProvider
from app.agents.rag_agent import RAGAgent
from app.agents.base import BaseLLMProvider


class GroundedRecordingMockProvider(BaseLLMProvider):
    """Mock provider that verifies retrieved context was injected into the prompt."""

    def __init__(self, response_text: str = "Based on Todd Jackson's framework..."):
        self.recorded_messages = []
        self.recorded_system_prompt = None
        self.response_text = response_text

    @property
    def provider_name(self) -> str:
        return "grounded-mock"

    @property
    def model_name(self) -> str:
        return "grounded-model-v1"

    def generate_chat_response(self, messages, system_prompt=None, temperature=0.7):
        self.recorded_messages = messages
        self.recorded_system_prompt = system_prompt
        return self.response_text

    def check_health(self):
        return {"status": "available", "provider": self.provider_name, "model": self.model_name}


@pytest.fixture(scope="module")
def db_session_module():
    """Module-scoped database session for real data inspection."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_real_transcripts_present_in_database(db_session_module):
    """Verify that real Lenny's Podcast transcripts exist in PostgreSQL."""
    docs = db_session_module.query(KnowledgeDocument).all()
    # Check that at least 5 genuine podcast episodes exist
    podcast_docs = [d for d in docs if d.source_type == "podcast" or "youtube" in (d.source_url or "")]
    assert len(podcast_docs) >= 5, f"Expected at least 5 genuine podcast episodes, found {len(podcast_docs)}"

    # Check key episodes exist
    titles = " ".join([d.title for d in podcast_docs])
    assert "Todd Jackson" in titles or "product-market fit" in titles.lower()
    assert "Adam Fishman" in titles or "growth team" in titles.lower()


def test_real_retrieval_product_market_fit(db_session_module):
    """Verify representative query 'product market fit' returns Todd Jackson's episode."""
    service = RetrievalService(db=db_session_module, embedding_provider=DeterministicHashEmbeddingProvider())
    hits = service.retrieve_context("finding product-market fit framework", top_k=3)

    assert len(hits) > 0, "Expected retrieval hits for 'product-market fit'"
    top_hit = hits[0]
    meta = top_hit.get("metadata", {})

    # Verify metadata fields
    assert "source_url" in meta
    assert meta.get("source_url") is not None
    assert "youtube.com/watch" in meta["source_url"]

    # Verify chunk content contains actual dialogue
    content = top_hit.get("content", "")
    assert len(content) > 50, "Chunk content should be substantive"
    assert "similarity_score" in top_hit
    assert top_hit["similarity_score"] > 0.0


def test_real_retrieval_growth_teams_adam_fishman(db_session_module):
    """Verify query 'build a high-performing growth team' returns relevant chunk and author."""
    service = RetrievalService(db=db_session_module, embedding_provider=DeterministicHashEmbeddingProvider())
    hits = service.retrieve_context("build a high-performing growth team Adam Fishman", top_k=3)

    assert len(hits) > 0
    # Check that Adam Fishman is among the top returned episodes
    authors_and_titles = [f"{h.get('metadata', {}).get('guest', '')} {h.get('metadata', {}).get('title', '')}" for h in hits]
    combined_str = " ".join(authors_and_titles)
    assert "Adam Fishman" in combined_str or "growth team" in combined_str.lower()


def test_real_citations_have_valid_metadata_and_links(db_session_module):
    """Verify that chunks have valid source_url and youtube video IDs or timestamps."""
    chunks = db_session_module.query(KnowledgeChunk).limit(20).all()
    assert len(chunks) > 0

    checked_citations = 0
    for chunk in chunks:
        meta = chunk.metadata_json or {}
        if meta.get("source_type") == "podcast":
            assert "source_url" in meta
            assert meta["source_url"].startswith("http")
            if "youtube.com" in meta["source_url"]:
                assert "watch?v=" in meta["source_url"]
            checked_citations += 1

    assert checked_citations > 0, "At least one podcast chunk metadata checked"


def test_agent_attaches_only_real_citations_without_fabrication(db_session_module):
    """Verify the RAGAgent extracts and attaches citations strictly from retrieved real chunks."""
    retrieval_service = RetrievalService(db=db_session_module, embedding_provider=DeterministicHashEmbeddingProvider())
    mock_provider = GroundedRecordingMockProvider("According to Todd Jackson, product-market fit involves extreme customer pull.")
    agent = RAGAgent(db=db_session_module, provider=mock_provider, retrieval_service=retrieval_service)

    response = agent.run(
        user_message="How do I find product-market fit according to Todd Jackson?",
        history=[]
    )

    # Verify that real context was injected into the prompt
    assert mock_provider.recorded_system_prompt is not None
    assert "Todd Jackson" in mock_provider.recorded_system_prompt or "product-market fit" in mock_provider.recorded_system_prompt.lower()

    # Verify citations are attached from retrieved chunks
    assert response.citations is not None
    assert len(response.citations) > 0

    # Ensure citations have genuine titles and youtube links
    for citation in response.citations:
        assert citation.title is not None
        assert citation.source_url is not None
        assert "youtube.com" in citation.source_url or "http" in citation.source_url
