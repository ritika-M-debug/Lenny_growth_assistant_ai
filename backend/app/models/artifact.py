import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Artifact(Base):
    """
    SQLAlchemy Model for AI-generated artifacts (Markdown documents, Ship 30 for 30 essays, HTML/CSS landing pages).
    Persisted in PostgreSQL and associated with conversations.
    """
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # 'markdown' or 'html'
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=True)  # Version, topic, citations, word count, render options
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    conversation = relationship("Conversation", back_populates="artifacts")
