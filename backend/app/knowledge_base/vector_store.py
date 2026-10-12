import math
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.knowledge_base.metadata import DocumentMetadata
from app.knowledge_base.chunker import TextChunk


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def is_document_ingested(db: Session, file_hash: str) -> bool:
    """Checks whether a document with the given content SHA256 hash already exists."""
    existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.file_hash == file_hash).first()
    return existing is not None


def extract_chunk_timestamp(content: str) -> tuple[Optional[str], Optional[int]]:
    """
    Extracts the earliest timestamp from a chunk's speaker line, e.g. (00:15:20) or (15:20).
    Returns (formatted_string, total_seconds).
    """
    # Look for (HH:MM:SS)
    match_long = re.search(r'\((\d{1,2}):(\d{2}):(\d{2})\)', content)
    if match_long:
        h, m, s = int(match_long.group(1)), int(match_long.group(2)), int(match_long.group(3))
        return f"{h:02d}:{m:02d}:{s:02d}", h * 3600 + m * 60 + s

    # Look for (MM:SS)
    match_short = re.search(r'\((\d{1,2}):(\d{2})\)', content)
    if match_short:
        m, s = int(match_short.group(1)), int(match_short.group(2))
        return f"{m:02d}:{s:02d}", m * 60 + s

    return None, None


def store_document_and_chunks(
    db: Session,
    metadata: DocumentMetadata,
    chunks: List[TextChunk],
    embeddings: List[List[float]]
) -> KnowledgeDocument:
    """
    Persists document metadata and text chunks with vector embeddings in PostgreSQL.
    Avoids duplicate ingestion if document file_hash exists.
    Preserves all podcast metadata and calculates timestamped YouTube URLs where available.
    """
    existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.file_hash == metadata.file_hash).first()
    if existing:
        return existing

    doc = KnowledgeDocument(
        title=metadata.title,
        source_type=metadata.source_type,
        author=metadata.author or metadata.guest,
        episode_title=metadata.episode_title,
        publication_date=metadata.publication_date,
        source_url=metadata.source_url or metadata.youtube_url,
        file_path=metadata.file_path,
        file_hash=metadata.file_hash,
        chunk_count=len(chunks)
    )
    db.add(doc)
    db.flush()  # Generates doc.id

    base_yt = metadata.youtube_url or (metadata.source_url if metadata.source_url and "youtube.com" in metadata.source_url else None)

    for chunk, emb in zip(chunks, embeddings):
        ts_str, ts_seconds = extract_chunk_timestamp(chunk.content)

        # Build timestamped YouTube link if valid YouTube URL and timestamp are present
        chunk_url = metadata.source_url or metadata.youtube_url
        if base_yt and ts_seconds is not None:
            sep = "&" if "?" in base_yt else "?"
            chunk_url = f"{base_yt}{sep}t={ts_seconds}s"

        meta_payload = {
            "document_id": str(doc.id),
            "chunk_index": chunk.chunk_index,
            "title": metadata.title,
            "source_type": metadata.source_type,
            "author": metadata.author or metadata.guest,
            "guest": metadata.guest,
            "episode_title": metadata.episode_title,
            "publication_date": metadata.publication_date,
            "source_url": chunk_url,
            "youtube_url": metadata.youtube_url,
            "video_id": metadata.video_id,
            "channel": metadata.channel,
            "timestamp": ts_str,
            "timestamp_seconds": ts_seconds,
            "char_count": chunk.char_count,
            "token_estimate": chunk.token_estimate,
            "file_path": metadata.file_path
        }
        # Filter out None values
        meta_payload = {k: v for k, v in meta_payload.items() if v is not None}

        chunk_record = KnowledgeChunk(
            document_id=doc.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            embedding=emb,
            token_count=chunk.token_estimate,
            metadata_json=meta_payload
        )
        db.add(chunk_record)

    db.commit()
    db.refresh(doc)
    return doc


def search_similar_chunks(
    db: Session,
    query_embedding: List[float],
    top_k: int = 5,
    min_similarity: float = 0.0,
    filter_guest: Optional[str] = None,
    filter_episode: Optional[str] = None,
    boost_terms: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves top_k most relevant text chunks using cosine similarity matching.
    Utilizes vectorized NumPy computations for fast execution across large collections.
    Supports guest/episode filtering and keyword/topic score boosting.
    """
    query = db.query(KnowledgeChunk)
    chunks = query.all()
    if not chunks:
        return []

    # Optional metadata pre-filtering (guest or episode)
    filtered = []
    for c in chunks:
        meta = c.metadata_json or {}
        if filter_guest:
            g_val = (meta.get("guest") or meta.get("author") or "").lower()
            if filter_guest.lower() not in g_val:
                continue
        if filter_episode:
            e_val = (meta.get("episode_title") or meta.get("title") or "").lower()
            if filter_episode.lower() not in e_val:
                continue
        filtered.append(c)

    if not filtered:
        return []

    # Fast NumPy Vectorized Cosine Similarity
    try:
        import numpy as np
        emb_matrix = np.array([c.embedding for c in filtered], dtype=np.float32)
        q_vec = np.array(query_embedding, dtype=np.float32)

        norms = np.linalg.norm(emb_matrix, axis=1) * np.linalg.norm(q_vec)
        norms[norms == 0] = 1e-10
        raw_sims = (emb_matrix @ q_vec) / norms
        sim_scores = raw_sims.tolist()
    except Exception:
        sim_scores = [cosine_similarity(query_embedding, c.embedding) for c in filtered]

    scored_results = []
    for chunk, sim in zip(filtered, sim_scores):
        score = float(sim)
        meta = chunk.metadata_json or {}

        # Keyword and topic boosting if boost_terms are provided
        if boost_terms:
            content_lower = chunk.content.lower()
            title_lower = (meta.get("title") or "").lower()
            guest_lower = (meta.get("guest") or meta.get("author") or "").lower()
            for term in boost_terms:
                t = term.lower()
                if t in guest_lower:
                    score += 0.08
                elif t in title_lower:
                    score += 0.04
                elif t in content_lower:
                    score += 0.02

        if score >= min_similarity:
            scored_results.append({
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "similarity_score": round(score, 4),
                "metadata": meta
            })

    # Sort descending by final similarity score
    scored_results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored_results[:top_k]
