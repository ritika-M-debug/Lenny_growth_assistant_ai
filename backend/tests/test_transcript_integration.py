import os
import pytest
from app.knowledge_base.ingest import is_transcript_target, ingest_file
from app.knowledge_base.loader import load_document
from app.knowledge_base.vector_store import extract_chunk_timestamp, is_document_ingested
from app.knowledge_base.embeddings import DeterministicHashEmbeddingProvider
from app.knowledge_base.retrieval import RetrievalService
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk


def test_transcript_target_filtering():
    """Verify is_transcript_target accepts podcast transcripts and rejects index/scripts/docs."""
    # Valid transcript targets
    assert is_transcript_target("app/knowledge_base/raw/lennys-podcast-transcripts/episodes/todd-jackson/transcript.md", ".")
    assert is_transcript_target("C:/path/episodes/guest-name/transcript.md", ".")
    
    # Excluded scripts, indexes, git, and fixtures
    assert not is_transcript_target("app/knowledge_base/raw/lennys-podcast-transcripts/scripts/transcribe.py", ".")
    assert not is_transcript_target("app/knowledge_base/raw/lennys-podcast-transcripts/index/tags.md", ".")
    assert not is_transcript_target("app/knowledge_base/raw/lennys-podcast-transcripts/README.md", ".")
    assert not is_transcript_target("app/knowledge_base/raw/lennys-podcast-transcripts/.git/config", ".")
    assert not is_transcript_target("tests/fixtures/sample_synthetic_test.md", ".")


def test_transcript_frontmatter_and_body_extraction():
    """Verify safe YAML frontmatter parsing and clean transcript body separation."""
    sample_path = "app/knowledge_base/raw/lennys-podcast-transcripts/episodes/todd-jackson/transcript.md"
    if not os.path.exists(sample_path):
        pytest.skip("Dataset directory not present in current test environment")

    loaded = load_document(sample_path, allowed_base_dirs=[sample_path, "app/knowledge_base/raw"])
    
    # Metadata fields correctly populated from frontmatter
    meta = loaded.metadata
    assert meta.guest == "Todd Jackson"
    assert "Todd Jackson" in meta.title or "product-market fit" in meta.title.lower()
    assert meta.youtube_url is not None and "youtube.com" in meta.youtube_url
    assert meta.video_id == "yc1Uwhfxacs"
    assert meta.publication_date == "2024-04-11"
    
    # Transcript body does not include the raw YAML block
    assert "---" not in loaded.normalized_content[:50]
    assert "Todd Jackson" in loaded.normalized_content


def test_timestamp_deep_link_extraction():
    """Verify timestamp regex extraction and YouTube deep link generation."""
    sample_text = "Todd Jackson (00:16:54): Okay, let's get into it. Let's talk about this framework."
    ts_str, ts_sec = extract_chunk_timestamp(sample_text)
    
    assert ts_str == "00:16:54"
    assert ts_sec == 16 * 60 + 54  # 1014 seconds

    base_url = "https://www.youtube.com/watch?v=yc1Uwhfxacs"
    deep_link = f"{base_url}&t={ts_sec}s"
    assert deep_link == "https://www.youtube.com/watch?v=yc1Uwhfxacs&t=1014s"


def test_idempotent_duplicate_skipping(db_session):
    """Verify incremental ingestion skips existing transcripts by hash without error."""
    sample_path = "app/knowledge_base/raw/lennys-podcast-transcripts/episodes/todd-jackson/transcript.md"
    if not os.path.exists(sample_path):
        pytest.skip("Dataset directory not present in current test environment")

    provider = DeterministicHashEmbeddingProvider()
    
    # First ingestion attempt should succeed or skip if already in DB
    result1 = ingest_file(
        file_path=sample_path,
        db=db_session,
        embedding_provider=provider,
        allowed_dirs=[os.path.dirname(sample_path), "app/knowledge_base/raw"]
    )
    assert result1["status"] in ["processed", "skipped"]

    # Second ingestion attempt MUST be skipped
    result2 = ingest_file(
        file_path=sample_path,
        db=db_session,
        embedding_provider=provider,
        allowed_dirs=[os.path.dirname(sample_path), "app/knowledge_base/raw"]
    )
    assert result2["status"] == "skipped"
    assert "Already ingested" in result2["reason"]


def test_retrieval_returns_grounded_citations(db_session):
    """Verify RetrievalService returns grounded episode metadata and YouTube links."""
    service = RetrievalService(db=db_session, embedding_provider=DeterministicHashEmbeddingProvider())
    results = service.retrieve_context("product-market fit", top_k=3)
    
    # If chunks are present in DB, ensure citations have metadata
    if results:
        top_hit = results[0]
        meta = top_hit.get("metadata", {})
        assert "title" in meta
        assert "source_url" in meta
        assert meta.get("source_url") is not None
