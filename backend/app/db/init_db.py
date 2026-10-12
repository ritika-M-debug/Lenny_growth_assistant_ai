import os
import time
import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import engine, Base, check_db_connection, SessionLocal
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.artifact import Artifact  # noqa: F401
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk  # noqa: F401

logger = logging.getLogger(__name__)

def wait_for_db(max_retries: int = 15, delay: float = 2.0) -> bool:
    """
    Polls the database until it becomes available or until max_retries is reached.
    Ensures the backend waits for PostgreSQL readiness in containerized environments.
    """
    for attempt in range(1, max_retries + 1):
        is_healthy, msg = check_db_connection()
        if is_healthy:
            logger.info("PostgreSQL database is ready (attempt %d/%d).", attempt, max_retries)
            return True
        logger.info("Waiting for PostgreSQL database to be ready (attempt %d/%d)...", attempt, max_retries)
        time.sleep(delay)
    logger.warning("PostgreSQL database was not ready after %d attempts.", max_retries)
    return False


def seed_transcripts_if_empty(session: Optional[Session] = None) -> int:
    """
    Checks if knowledge_documents has 0 records. If empty, automatically ingests
    the curated set of genuine Lenny podcast transcripts so the RAG knowledge base
    is immediately functional in fresh deployments (e.g. Render, Docker, fresh PostgreSQL).
    Idempotent: skips immediately if transcripts are already present.
    """
    from app.knowledge_base.ingest import ingest_file
    from app.knowledge_base.embeddings import get_hash_provider

    db = session or SessionLocal()
    close_db = session is None

    try:
        count = db.query(KnowledgeDocument).count()
        if count > 0:
            logger.info("Knowledge base already populated (%d documents). Skipping auto-seeding.", count)
            return count

        logger.info("Knowledge base is empty. Running automatic seeding of curated Lenny podcast transcripts...")

        # Determine episodes directory location relative to app package
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        episodes_dir = os.path.join(app_dir, "knowledge_base", "raw", "lennys-podcast-transcripts", "episodes")

        # Curated core episodes covering Product-Market Fit, Growth Teams, Strategy, Onboarding, and Career
        curated_episodes = [
            "todd-jackson",      # A framework for finding product-market fit
            "adam-fishman",      # How to build a high-performing growth team
            "elena-verna",       # 10 growth tactics that never work
            "rahul-vohra",       # Superhuman's secret to success
            "lauryn-isford",     # Mastering onboarding
            "ada-chen-rekhi",    # Feeling stuck? When it's time to leave your job
        ]

        provider = get_hash_provider()
        seeded_count = 0

        for ep_slug in curated_episodes:
            transcript_path = os.path.join(episodes_dir, ep_slug, "transcript.md")
            if os.path.isfile(transcript_path):
                try:
                    res = ingest_file(
                        file_path=transcript_path,
                        db=db,
                        embedding_provider=provider,
                        chunk_size=1000,
                        chunk_overlap=200,
                        allowed_dirs=[episodes_dir]
                    )
                    if res.get("status") in ["processed", "skipped"]:
                        seeded_count += 1
                except Exception as ingest_err:
                    logger.warning("Error auto-seeding episode %s: %s", ep_slug, ingest_err)

        # Also ingest synthetic sample if present
        synthetic_path = os.path.join(app_dir, "knowledge_base", "raw", "sample_synthetic_test.md")
        if os.path.isfile(synthetic_path):
            try:
                ingest_file(
                    file_path=synthetic_path,
                    db=db,
                    embedding_provider=provider,
                    chunk_size=1000,
                    chunk_overlap=200,
                    allowed_dirs=[app_dir]
                )
            except Exception as e:
                logger.debug("Synthetic sample seed note: %s", e)

        logger.info("Auto-seeding complete. Ingested %d core podcast episodes into PostgreSQL.", seeded_count)
        return seeded_count

    except Exception as e:
        logger.error("Failed during knowledge base auto-seeding: %s", e)
        return 0
    finally:
        if close_db:
            db.close()


def init_db(wait: bool = True) -> None:
    """
    Safely initializes database tables for defined SQLAlchemy models.
    Waits for DB readiness, then runs Base.metadata.create_all.
    Does not drop tables or delete existing data.
    Ensures newly added columns exist without disrupting existing data.
    Automatically seeds curated Lenny podcast transcripts if knowledge base is empty.
    """
    if wait:
        wait_for_db()

    try:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            # Safely add metadata_json column to messages if missing in PostgreSQL
            try:
                conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS metadata_json JSONB;"))
                conn.commit()
            except Exception as migration_err:
                logger.debug(f"Column migration check note: {migration_err}")
        logger.info("Database tables initialized successfully.")

        # Ensure knowledge base is populated with curated Lenny transcripts
        seed_transcripts_if_empty()

    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
