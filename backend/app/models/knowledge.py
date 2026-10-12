import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.db.session import Base

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False, default="document")  # e.g., 'podcast', 'newsletter', 'document', 'synthetic_test'
    author = Column(String(255), nullable=True)
    episode_title = Column(String(255), nullable=True)
    publication_date = Column(String(100), nullable=True)
    source_url = Column(Text, nullable=True)
    file_path = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False, unique=True, index=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSONB, nullable=False)  # JSONB array of float embeddings for 100% PostgreSQL compatibility
    token_count = Column(Integer, nullable=False, default=0)
    metadata_json = Column(JSONB, nullable=False)  # Grounded source metadata payload
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        Index("idx_knowledge_chunk_doc_index", "document_id", "chunk_index"),
    )
