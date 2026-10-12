from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

class ArtifactCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Human-readable title of the artifact")
    type: Literal["markdown", "html"] = Field(..., description="Artifact document type ('markdown' or 'html')")
    content: str = Field(..., min_length=1, max_length=500_000, description="Full artifact code/content")
    metadata_json: Optional[dict] = Field(default=None, description="Optional metadata (topic, word_count, citations)")

class ArtifactUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content: Optional[str] = Field(default=None, min_length=1, max_length=500_000)
    metadata_json: Optional[dict] = None

class ArtifactRead(BaseModel):
    id: str
    conversation_id: str
    title: str
    type: str
    content: str
    metadata_json: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
