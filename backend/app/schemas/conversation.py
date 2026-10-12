from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=50_000, description="Message text content")

class MessageRead(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    metadata_json: Optional[dict] = None
    citations: Optional[List[dict]] = None
    artifact: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default="New Conversation", max_length=255)

class ConversationRead(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConversationDetailRead(ConversationRead):
    messages: List[MessageRead] = []

    model_config = ConfigDict(from_attributes=True)
