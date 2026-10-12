import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.knowledge_base.normalizer import normalize_text
from app.knowledge_base.chunker import chunk_text
from app.knowledge_base.metadata import extract_metadata, compute_file_hash
from app.knowledge_base.loader import load_document
from app.knowledge_base.embeddings import DeterministicHashEmbeddingProvider
from app.knowledge_base.vector_store import store_document_and_chunks, is_document_ingested
from app.knowledge_base.retrieval import RetrievalService
from app.knowledge_base.ingest import ingest_file

# Set up isolated in-memory SQLite database for RAG tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_normalize_text():
    raw = "Header Line\r\n\r\n  Body text with   multiple   spaces.\x07\x08"
    normalized = normalize_text(raw)
    assert "\r" not in normalized
    assert "  Body" not in normalized
    assert "\x07" not in normalized
    assert normalized == "Header Line\n\nBody text with multiple spaces."


def test_chunk_text():
    text = "Paragraph 1 is about product market fit and retention.\n\nParagraph 2 covers user activation metrics and aha moments.\n\nParagraph 3 explains growth loops and acquisition channels."
    chunks = chunk_text(text, chunk_size=80, chunk_overlap=20)
    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].token_estimate > 0
    assert chunks[0].char_count > 0


def test_metadata_preservation():
    raw_content = """---
title: Product Strategy Playbook
author: Elena Verna
type: podcast
episode_title: Growth Loops Masterclass
publication_date: 2026-05-15
source_url: https://example.com/podcast/growth-loops
---
This is the transcript content.
"""
    meta = extract_metadata("sample_podcast.md", raw_content)
    assert meta.title == "Product Strategy Playbook"
    assert meta.author == "Elena Verna"
    assert meta.source_type == "podcast"
    assert meta.episode_title == "Growth Loops Masterclass"
    assert meta.publication_date == "2026-05-15"
    assert meta.source_url == "https://example.com/podcast/growth-loops"
    assert meta.file_hash == compute_file_hash(raw_content)


def test_metadata_missing_fields_not_fabricated():
    raw_content = "Plain text without headers."
    meta = extract_metadata("plain_note.txt", raw_content)
    assert meta.title == "Plain Note"
    assert meta.author is None
    assert meta.episode_title is None
    assert meta.publication_date is None
    assert meta.source_url is None


def test_load_empty_and_unsupported_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test non-existent file
        with pytest.raises(FileNotFoundError):
            load_document(os.path.join(tmp_dir, "missing.txt"), allowed_base_dirs=[tmp_dir])

        # Test unsupported format
        unsupported = os.path.join(tmp_dir, "test.doc")
        with open(unsupported, "w") as f:
            f.write("data")
        with pytest.raises(ValueError, match="Unsupported file format"):
            load_document(unsupported, allowed_base_dirs=[tmp_dir])

        # Test empty file
        empty_file = os.path.join(tmp_dir, "empty.txt")
        with open(empty_file, "w") as f:
            f.write("   \n ")
        with pytest.raises(ValueError, match="is empty"):
            load_document(empty_file, allowed_base_dirs=[tmp_dir])


def test_duplicate_ingestion_behavior():
    db = TestingSessionLocal()
    provider = DeterministicHashEmbeddingProvider()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "synth_doc.md")
        content = "Synthetic test content for duplicate checking."
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # First ingestion -> processed
        res1 = ingest_file(file_path, db, provider, allowed_dirs=[tmp_dir])
        assert res1["status"] == "processed"
        assert res1["chunks"] > 0

        # Second ingestion -> skipped due to identical hash
        res2 = ingest_file(file_path, db, provider, allowed_dirs=[tmp_dir])
        assert res2["status"] == "skipped"
        assert "identical content hash" in res2["reason"]


def test_empty_knowledge_base_retrieval():
    db = TestingSessionLocal()
    retrieval_service = RetrievalService(db=db, embedding_provider=DeterministicHashEmbeddingProvider())
    results = retrieval_service.retrieve_context("What is retention?")
    assert results == []
    formatted = retrieval_service.format_context_for_prompt(results)
    assert formatted == "No relevant knowledge base context found."


def test_retrieval_ranking_synthetic_docs():
    db = TestingSessionLocal()
    provider = DeterministicHashEmbeddingProvider()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create synthetic test file 1: User Activation
        f1_path = os.path.join(tmp_dir, "synthetic_activation.md")
        f1_content = """---
title: Synthetic Test: User Activation
type: synthetic_test
author: Test Author
---
User activation is the process of guiding new users to their first Aha! moment quickly.
Key metrics include onboarding completion rate, time-to-value, and core action frequency.
"""
        with open(f1_path, "w", encoding="utf-8") as f:
            f.write(f1_content)

        # Create synthetic test file 2: Monetization
        f2_path = os.path.join(tmp_dir, "synthetic_monetization.md")
        f2_content = """---
title: Synthetic Test: Pricing and Monetization
type: synthetic_test
author: Test Author
---
Monetization strategies involve value-based pricing tiers, freemium conversion, and expansion revenue.
Reducing customer churn increases lifetime value (LTV).
"""
        with open(f2_path, "w", encoding="utf-8") as f:
            f.write(f2_content)

        # Ingest synthetic documents
        ingest_file(f1_path, db, provider, allowed_dirs=[tmp_dir])
        ingest_file(f2_path, db, provider, allowed_dirs=[tmp_dir])

        # Execute query retrieval
        retrieval_service = RetrievalService(db=db, embedding_provider=provider)
        results = retrieval_service.retrieve_context("How do I improve user activation and time to value?", top_k=2)

        assert len(results) > 0
        top_result = results[0]
        assert top_result["similarity_score"] > 0.0
        assert "user activation" in top_result["content"].lower() or "aha! moment" in top_result["content"].lower()
        assert top_result["metadata"]["title"] == "Synthetic Test: User Activation"
        assert top_result["metadata"]["author"] == "Test Author"

        # Format context prompt check
        prompt_context = retrieval_service.format_context_for_prompt(results)
        assert "Source [1]: Synthetic Test: User Activation" in prompt_context
