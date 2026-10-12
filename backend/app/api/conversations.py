from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.conversation import Conversation, Message
from app.models.artifact import Artifact
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationDetailRead,
    MessageCreate,
    MessageRead
)
import logging
from app.agents.rag_agent import RAGAgent
from app.agents.base import (
    ProviderError,
    ProviderConfigurationError,
    ProviderUnavailableError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ProviderTimeoutError,
)
from app.core.sanitizer import sanitize_html

logger = logging.getLogger("lenny_assistant.api.conversations")
router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate = ConversationCreate(),
    db: Session = Depends(get_db)
):
    """
    Creates a new conversation record in PostgreSQL.
    """
    try:
        title = payload.title.strip() if payload.title and payload.title.strip() else "New Conversation"
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            title=title,
            created_at=now,
            updated_at=now
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation in database. Verify PostgreSQL credentials."
        )


@router.get("", response_model=List[ConversationRead])
def list_conversations(db: Session = Depends(get_db)):
    """
    Lists all conversations ordered by updated_at descending (newest updated first).
    Returns empty list gracefully if DB is unreachable or credentials invalid.
    """
    try:
        conversations = db.query(Conversation).order_by(desc(Conversation.updated_at)).all()
        return conversations
    except Exception as e:
        print(f"Notice: Database query failed ({e}). Returning empty list.")
        return []


@router.get("/{conversation_id}", response_model=ConversationDetailRead)
def get_conversation_detail(conversation_id: str, db: Session = Depends(get_db)):
    """
    Retrieves a conversation by ID along with all associated messages in chronological order.
    Returns 404 if conversation does not exist.
    """
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failure. Verify PostgreSQL credentials."
        )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID '{conversation_id}' was not found."
        )
    
    # Format citations and artifacts onto messages if present in metadata_json
    for msg in conversation.messages:
        if msg.metadata_json:
            if "citations" in msg.metadata_json:
                msg.citations = msg.metadata_json["citations"]
            if "artifact" in msg.metadata_json:
                msg.artifact = msg.metadata_json["artifact"]

    return conversation


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def create_message_in_conversation(
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Saves user message, runs RAGAgent to retrieve grounded context and generate AI response,
    persists assistant response with citations, and updates conversation timestamp.
    """
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failure. Verify PostgreSQL credentials."
        )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID '{conversation_id}' was not found."
        )

    now = datetime.now(timezone.utc)

    # 1. Save User Message FIRST (guarantees message is not lost even if model fails)
    try:
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=payload.content,
            created_at=now
        )
        db.add(user_msg)

        # Update Conversation Title if default 'New Conversation'
        if conversation.title == "New Conversation" and payload.content:
            derived_title = payload.content.strip()[:40]
            if len(payload.content.strip()) > 40:
                derived_title += "..."
            conversation.title = derived_title

        conversation.updated_at = now
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Failed to persist user message in database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist user message in database."
        )

    # 2. Extract conversation history for RAGAgent
    existing_messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    history_payload = [
        {"role": m.role, "content": m.content}
        for m in existing_messages if m.role in ["user", "assistant"]
    ]

    # 3. Run RAGAgent to generate grounded response
    agent = RAGAgent(db=db)
    try:
        agent_resp = agent.run(user_message=payload.content, history=history_payload[:-1])
        assistant_content = agent_resp.content
        meta_payload = agent_resp.to_dict()

        # If agent produced an artifact (Markdown document, essay, or HTML landing page), persist it in PostgreSQL
        if agent_resp.extra_metadata and "artifact_content" in agent_resp.extra_metadata:
            art_type = agent_resp.extra_metadata.get("artifact_type", "markdown")
            art_title = agent_resp.extra_metadata.get("artifact_title") or "Generated Artifact"
            art_content = agent_resp.extra_metadata.get("artifact_content", "")

            # Sanitize HTML before persisting
            clean_art_content = sanitize_html(art_content) if art_type == "html" else art_content

            try:
                artifact_record = Artifact(
                    conversation_id=conversation_id,
                    title=art_title,
                    type=art_type,
                    content=clean_art_content,
                    metadata_json=agent_resp.extra_metadata
                )
                db.add(artifact_record)
                db.commit()
                db.refresh(artifact_record)

                # Attach persisted artifact reference to message metadata
                meta_payload["artifact"] = {
                    "id": str(artifact_record.id),
                    "title": artifact_record.title,
                    "type": artifact_record.type,
                    "content": artifact_record.content
                }
            except Exception as art_err:
                print(f"Notice: Artifact persistence error: {art_err}")
                db.rollback()

    except Exception as err:
        err_str = str(err)
        provider_name = getattr(agent.provider, "provider_name", "unknown")
        model_name = getattr(agent.provider, "model_name", "unknown")
        logger.warning(
            "Agent generation error [provider=%s, model=%s]: %s",
            provider_name, model_name, err_str
        )

        if (
            isinstance(err, ProviderAuthenticationError)
            or "authentication" in err_str.lower()
            or "api_key" in err_str.lower()
            or "401" in err_str
        ):
            assistant_content = (
                "⚠️ Anthropic API authentication failed. "
                "Please verify that your ANTHROPIC_API_KEY is configured correctly in backend/.env, "
                "or switch to local inference by setting LLM_PROVIDER=ollama."
            )
            safe_detail = "Anthropic API authentication failed (401 or invalid key)."
        elif isinstance(err, ProviderRateLimitError) or "rate limit" in err_str.lower() or "429" in err_str:
            assistant_content = (
                "⚠️ Cloud AI rate limit reached. "
                "The Anthropic API rate limit was exceeded. Please wait a moment before sending another message."
            )
            safe_detail = "Anthropic API rate limit reached (429)."
        elif isinstance(err, ProviderModelNotFoundError) or ("not found" in err_str.lower() and "model" in err_str.lower()):
            assistant_content = (
                f"⚠️ Model '{model_name}' was not found. "
                f"Please ensure it is installed (`ollama pull {model_name}`) or select an available model."
            )
            safe_detail = f"Model '{model_name}' not found."
        elif isinstance(err, ProviderTimeoutError) or "timed out" in err_str.lower() or "timeout" in err_str.lower():
            assistant_content = (
                "⚠️ The AI model request timed out before completing. "
                "Please try again with a shorter query or increase the timeout in your configuration."
            )
            safe_detail = "Model generation timeout."
        elif isinstance(err, ProviderUnavailableError) or "connect" in err_str.lower() or "connection" in err_str.lower():
            if provider_name == "ollama":
                assistant_content = (
                    "⚠️ The local Ollama model service is currently unreachable. "
                    "Please verify that Ollama is installed and running (`ollama serve`), then retry your request."
                )
                safe_detail = "Ollama connection failure."
            else:
                assistant_content = (
                    f"⚠️ The {provider_name} service is currently unreachable. "
                    "Please check your internet connection or service status and retry."
                )
                safe_detail = f"{provider_name} network connection failure."
        elif isinstance(err, ProviderConfigurationError) or "configuration" in err_str.lower() or "unsupported" in err_str.lower():
            assistant_content = (
                f"⚠️ LLM Configuration Error: {err_str} "
                "Please check your settings in backend/.env."
            )
            safe_detail = "LLM configuration error."
        else:
            assistant_content = (
                "⚠️ An issue occurred while generating a response from the AI assistant. "
                "Please check the service status and try again."
            )
            safe_detail = "AI service generation error."

        meta_payload = {
            "status": "error",
            "error_detail": safe_detail,
            "citations": [],
            "provider": provider_name,
            "model": model_name
        }

    # 4. Save Assistant Response
    try:
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            metadata_json=meta_payload,
            created_at=datetime.now(timezone.utc)
        )
        db.add(assistant_msg)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assistant_msg)

        if meta_payload and "citations" in meta_payload:
            assistant_msg.citations = meta_payload["citations"]
        if meta_payload and "artifact" in meta_payload:
            assistant_msg.artifact = meta_payload["artifact"]

        return assistant_msg
    except Exception as e:
        db.rollback()
        logger.error("Failed to persist assistant response in database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist assistant response in database."
        )


@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """
    Deletes a conversation and all its associated messages via database cascade.
    """
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failure. Verify PostgreSQL credentials."
        )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID '{conversation_id}' was not found."
        )

    try:
        db.delete(conversation)
        db.commit()
        return {"message": f"Conversation '{conversation_id}' deleted successfully."}
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation from database."
        )
