import time
import logging
from sqlalchemy import text
from app.db.session import engine, Base, check_db_connection
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

def init_db(wait: bool = True) -> None:
    """
    Safely initializes database tables for defined SQLAlchemy models.
    Waits for DB readiness, then runs Base.metadata.create_all.
    Does not drop tables or delete existing data.
    Ensures newly added columns exist without disrupting existing data.
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
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
