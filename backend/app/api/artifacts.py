from typing import List
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.artifact import Artifact
from app.schemas.artifact import ArtifactCreate, ArtifactUpdate, ArtifactRead
from app.core.sanitizer import sanitize_html, validate_artifact_payload

logger = logging.getLogger("lenny_assistant.api.artifacts")
router = APIRouter(tags=["Artifacts"])


@router.post("/conversations/{conversation_id}/artifacts", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
def create_artifact_for_conversation(
    conversation_id: str,
    payload: ArtifactCreate,
    db: Session = Depends(get_db)
):
    """
    Creates and persists a new artifact associated with an existing conversation.
    Validates payload constraints and sanitizes HTML content.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID '{conversation_id}' was not found."
        )

    # Validate type and size
    is_valid, err_msg = validate_artifact_payload(payload.title, payload.type, payload.content)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg
        )

    # Sanitize content if HTML
    clean_content = sanitize_html(payload.content) if payload.type == "html" else payload.content

    try:
        artifact = Artifact(
            conversation_id=conversation_id,
            title=payload.title.strip(),
            type=payload.type,
            content=clean_content,
            metadata_json=payload.metadata_json
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        return artifact
    except Exception as e:
        db.rollback()
        logger.error("Failed to persist artifact: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist artifact in database."
        )


@router.get("/conversations/{conversation_id}/artifacts", response_model=List[ArtifactRead])
def list_artifacts_for_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    Lists all artifacts belonging to a specific conversation, ordered chronologically descending.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID '{conversation_id}' was not found."
        )

    artifacts = db.query(Artifact).filter(
        Artifact.conversation_id == conversation_id
    ).order_by(Artifact.created_at.desc()).all()

    return artifacts


@router.get("/artifacts/{artifact_id}", response_model=ArtifactRead)
def get_artifact_by_id(
    artifact_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves an artifact by its unique ID.
    """
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact with ID '{artifact_id}' was not found."
        )
    return artifact


@router.put("/artifacts/{artifact_id}", response_model=ArtifactRead)
def update_artifact_by_id(
    artifact_id: str,
    payload: ArtifactUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates the title, content, or metadata of an existing artifact.
    """
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact with ID '{artifact_id}' was not found."
        )

    if payload.title is not None:
        if not payload.title.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title cannot be empty.")
        artifact.title = payload.title.strip()

    if payload.content is not None:
        if not payload.content.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content cannot be empty.")
        if len(payload.content) > 500_000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content exceeds 500,000 characters.")
        artifact.content = sanitize_html(payload.content) if artifact.type == "html" else payload.content

    if payload.metadata_json is not None:
        artifact.metadata_json = payload.metadata_json

    try:
        db.commit()
        db.refresh(artifact)
        return artifact
    except Exception as e:
        db.rollback()
        logger.error("Failed to update artifact: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update artifact in database."
        )


@router.delete("/artifacts/{artifact_id}", status_code=status.HTTP_200_OK)
def delete_artifact_by_id(
    artifact_id: str,
    db: Session = Depends(get_db)
):
    """
    Deletes an artifact by ID.
    """
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact with ID '{artifact_id}' was not found."
        )

    try:
        db.delete(artifact)
        db.commit()
        return {"status": "deleted", "id": artifact_id}
    except Exception as e:
        db.rollback()
        logger.error("Failed to delete artifact: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete artifact from database."
        )
