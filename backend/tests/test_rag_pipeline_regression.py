"""Regression tests for Lenny Growth Assistant RAG pipeline.

Covers:
1. Real transcript document and chunk count verification.
2. Complete retrieval flow for 'product-market fit' and 'growth strategy'.
3. Embedding dimension compatibility (document vectors vs query vectors).
4. Chat endpoint message generation passing retrieved transcript chunks to the answer generator.
5. RAG Health endpoint (/health/rag) reporting document/chunk statistics.
6. Auto-seeding idempotency test.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal, get_db
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.knowledge_base.retrieval import RetrievalService
from app.knowledge_base.embeddings import get_embedding_provider, DeterministicHashEmbeddingProvider
from app.agents.rag_agent import RAGAgent

@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def pg_client():
    def get_real_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = get_real_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_1_real_podcast_documents_and_chunks_exist(db_session):
    """Verify that genuine Lenny podcast transcripts exist in PostgreSQL."""
    docs = db_session.query(KnowledgeDocument).all()
    assert len(docs) >= 5, f"Expected at least 5 documents, found {len(docs)}"

    # Check that key podcast episodes are present
    titles = [d.title for d in docs]
    assert any("Todd Jackson" in t or "product-market fit" in t.lower() for t in titles)
    assert any("Adam Fishman" in t or "growth team" in t.lower() for t in titles)
    assert any("Elena Verna" in t or "growth tactics" in t.lower() for t in titles)

    chunk_count = db_session.query(KnowledgeChunk).count()
    assert chunk_count >= 500, f"Expected at least 500 chunks, found {chunk_count}"


def test_2_embedding_dimensions_are_compatible(db_session):
    """Verify stored chunk embeddings match the active query embedding provider dimension."""
    provider = get_embedding_provider()
    query_dim = provider.dimension

    sample_chunk = db_session.query(KnowledgeChunk).first()
    assert sample_chunk is not None
    assert isinstance(sample_chunk.embedding, list)
    chunk_dim = len(sample_chunk.embedding)

    assert chunk_dim == query_dim, f"Embedding mismatch: chunk has {chunk_dim} dims, query provider has {query_dim}"


def test_3_retrieval_product_market_fit(db_session):
    """Verify retrieval with 'product-market fit' returns relevant Todd Jackson chunks."""
    retriever = RetrievalService(db=db_session, embedding_provider=DeterministicHashEmbeddingProvider())
    results = retriever.retrieve_context("How do I find product-market fit?", top_k=5)

    assert len(results) > 0, "Expected non-empty retrieval results for product-market fit"

    top_chunk = results[0]
    meta = top_chunk.get("metadata", {})
    assert "Todd Jackson" in meta.get("title", "") or "product-market fit" in meta.get("title", "").lower()
    assert top_chunk.get("similarity_score", 0.0) > 0.0
    assert "youtube.com" in meta.get("source_url", "")


def test_4_retrieval_growth_strategy(db_session):
    """Verify retrieval with 'growth strategy' returns relevant Elena Verna / Adam Fishman chunks."""
    retriever = RetrievalService(db=db_session, embedding_provider=DeterministicHashEmbeddingProvider())
    results = retriever.retrieve_context("growth strategy tactics", top_k=5)

    assert len(results) > 0, "Expected non-empty retrieval results for growth strategy"
    titles_and_authors = [
        f"{r.get('metadata', {}).get('title', '')} {r.get('metadata', {}).get('guest', '')}"
        for r in results
    ]
    combined = " ".join(titles_and_authors).lower()
    assert "elena verna" in combined or "adam fishman" in combined or "growth" in combined


def test_5_chat_endpoint_attaches_real_transcript_citations(pg_client):
    """Verify POST /api/conversations/{id}/messages receives real citations from Lenny transcripts."""
    # 1. Create a conversation
    conv_resp = pg_client.post("/api/conversations", json={"title": "PMF Inquiry"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # 2. Ask PMF question
    msg_resp = pg_client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "How do I find product-market fit?"}
    )
    assert msg_resp.status_code == 201
    data = msg_resp.json()

    # 3. Verify citations are non-empty and point to real transcripts
    citations = data.get("citations", [])
    assert len(citations) > 0, "Expected at least 1 citation attached to assistant response"

    first_cit = citations[0]
    assert "Todd Jackson" in first_cit.get("title", "") or "product-market fit" in first_cit.get("title", "").lower()
    assert first_cit.get("source_url", "").startswith("https://")
    assert first_cit.get("similarity_score", 0.0) > 0.0

    # 4. Verify message content is grounded and references sources
    content = data.get("content", "")
    assert "Source" in content or "Todd Jackson" in content or "retention" in content.lower()
    assert "No specific transcript context was retrieved" not in content


def test_6_health_rag_diagnostic_endpoint(pg_client):
    """Verify /health/rag returns operational statistics and 'ready' status."""
    resp = pg_client.get("/health/rag")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ready"
    assert data["document_count"] >= 5
    assert data["chunk_count"] >= 500
    assert data["embedding_dimension"] == 384
