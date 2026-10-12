import argparse
import os
import sys
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.init_db import init_db

from app.knowledge_base.loader import load_document
from app.knowledge_base.chunker import chunk_text
from app.knowledge_base.metadata import compute_file_hash
from app.knowledge_base.embeddings import get_embedding_provider, BaseEmbeddingProvider
from app.knowledge_base.vector_store import is_document_ingested, store_document_and_chunks


def is_transcript_target(file_path: str, scan_root: str) -> bool:
    """
    Determines whether a file is an approved transcript target.
    Excludes scripts/, index/, .git/, and non-transcript documentation.
    """
    norm_path = os.path.normpath(file_path).replace("\\", "/")
    filename = os.path.basename(norm_path).lower()

    # Disallowed directories and files
    disallowed_dirs = ["/scripts/", "/index/", "/.git/", "/test_fixtures/", "/fixtures/"]
    if any(d in norm_path for d in disallowed_dirs):
        return False

    if filename in ["readme.md", "claude.md", ".gitkeep", ".gitignore"]:
        return False

    # Primary podcast source is transcript.md
    if filename == "transcript.md":
        return True

    # Also support top-level markdown files if placed directly in raw/
    if filename.endswith(".md") or filename.endswith(".txt"):
        return True

    return False


def ingest_file(
    file_path: str,
    db: Session,
    embedding_provider: BaseEmbeddingProvider,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    allowed_dirs: List[str] = None,
    batch_size: int = 64
) -> Dict[str, Any]:
    """
    Ingests a single file into PostgreSQL safely and idempotently.
    Embeds chunks in memory-safe batches and preserves episode metadata.
    """
    try:
        loaded = load_document(file_path, allowed_base_dirs=allowed_dirs)
    except Exception as e:
        return {"status": "failed", "file": file_path, "error": str(e), "chunks": 0}

    # Check for duplicate ingestion via file SHA256 hash
    if is_document_ingested(db, loaded.metadata.file_hash):
        return {
            "status": "skipped",
            "file": file_path,
            "title": loaded.metadata.title,
            "reason": "Already ingested (identical content hash)",
            "chunks": 0
        }

    # Chunk normalized text body
    chunks = chunk_text(loaded.normalized_content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        return {"status": "failed", "file": file_path, "error": "No valid text chunks produced", "chunks": 0}

    # Generate embeddings in memory-safe batches
    embeddings: List[List[float]] = []
    chunk_texts = [c.content for c in chunks]

    for i in range(0, len(chunk_texts), batch_size):
        sub_batch = chunk_texts[i : i + batch_size]
        sub_embeddings = embedding_provider.embed_batch(sub_batch)
        embeddings.extend(sub_embeddings)

    # Store document and chunks in PostgreSQL
    doc = store_document_and_chunks(db, loaded.metadata, chunks, embeddings)

    return {
        "status": "processed",
        "file": file_path,
        "title": doc.title,
        "author": doc.author,
        "document_id": str(doc.id),
        "chunks": len(chunks)
    }


def ingest_directory(
    directory_path: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    provider_name: str = None,
    limit: Optional[int] = None,
    batch_size: int = 64
) -> Dict[str, Any]:
    """
    Scans a directory recursively and ingests valid transcript files.
    Skips index/, scripts/, and duplicate records idempotently.
    """
    abs_dir = os.path.abspath(directory_path)
    if not os.path.exists(abs_dir):
        return {
            "discovered": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 1,
            "total_chunks": 0,
            "details": [{"file": directory_path, "status": "failed", "error": "Directory does not exist"}]
        }

    init_db()  # Ensure database tables exist
    db = SessionLocal()
    provider = get_embedding_provider(provider_name)

    stats = {
        "discovered": 0,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "total_chunks": 0,
        "details": []
    }

    try:
        # 1. Discover target transcript files recursively
        discovered_files = []
        for root, dirs, files in os.walk(abs_dir):
            # Prune disallowed directories from walking
            dirs[:] = [d for d in dirs if d not in [".git", "scripts", "index"]]

            for file in files:
                file_full = os.path.join(root, file)
                if is_transcript_target(file_full, abs_dir):
                    discovered_files.append(file_full)

        discovered_files.sort()
        stats["discovered"] = len(discovered_files)

        if limit and limit > 0:
            discovered_files = discovered_files[:limit]

        total_to_process = len(discovered_files)
        print(f"Discovered {stats['discovered']} transcript files. Processing {total_to_process} files...")

        # 2. Ingest files sequentially with progress reporting
        for idx, file_path in enumerate(discovered_files, start=1):
            rel_name = os.path.relpath(file_path, abs_dir)
            print(f"[{idx}/{total_to_process}] Ingesting: {rel_name}...", end=" ", flush=True)

            res = ingest_file(
                file_path=file_path,
                db=db,
                embedding_provider=provider,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                allowed_dirs=[abs_dir],
                batch_size=batch_size
            )
            stats["details"].append(res)

            if res["status"] == "processed":
                stats["processed"] += 1
                stats["total_chunks"] += res["chunks"]
                print(f"DONE ({res['chunks']} chunks, '{res.get('title')}')")
            elif res["status"] == "skipped":
                stats["skipped"] += 1
                print(f"SKIPPED ({res.get('reason')})")
            else:
                stats["failed"] += 1
                print(f"FAILED ({res.get('error')})")

    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Lenny's Podcast Transcript Ingestion Pipeline for PostgreSQL RAG.")
    parser.add_argument(
        "--dir",
        type=str,
        default="app/knowledge_base/raw/lennys-podcast-transcripts/episodes",
        help="Directory containing transcript source files (default: episodes/ folder)."
    )
    parser.add_argument("--chunk-size", type=int, default=1000, help="Target character length per chunk (default 1000).")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Overlap character count between chunks (default 200).")
    parser.add_argument("--provider", type=str, default=None, help="Embedding provider (sentence-transformers, hash, ollama, openai).")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of transcript files to process.")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding inference batch size (default 64).")

    args = parser.parse_args()

    print(f"Starting transcript ingestion scan on: {args.dir}")
    summary = ingest_directory(
        directory_path=args.dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        provider_name=args.provider,
        limit=args.limit,
        batch_size=args.batch_size
    )

    print("\n================ Ingestion Summary ================")
    print(f"Transcript Files Discovered:  {summary['discovered']}")
    print(f"Files Processed Successfully: {summary['processed']}")
    print(f"Files Skipped (Duplicates):   {summary['skipped']}")
    print(f"Files Failed:                 {summary['failed']}")
    print(f"Total Chunks Created:         {summary['total_chunks']}")
    print("===================================================\n")


if __name__ == "__main__":
    main()
