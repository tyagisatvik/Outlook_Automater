"""Email API endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from app.db.database import get_db
from app.db.models import Email
from app.core.security import get_current_user_id
from app.services.vector_store import vector_store

router = APIRouter()


class EmailResponse(BaseModel):
    """Email response model"""
    id: int
    message_id: str
    subject: str
    sender: dict
    summary: Optional[str]
    key_points: Optional[List[str]]
    suggested_actions: Optional[List[dict]]
    received_at: str
    is_read: bool
    urgency_score: Optional[float]
    category: Optional[str]


class SimilarEmailResponse(BaseModel):
    """Similar email response model"""
    email_id: str
    similarity: float
    subject: str
    sender: str
    preview: str


@router.get("/", response_model=List[EmailResponse])
async def list_emails(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False)
):
    """
    List emails for authenticated user with pagination

    Args:
        user_id: User ID from JWT
        db: Database session
        skip: Number of emails to skip
        limit: Maximum number of emails to return
        unread_only: Filter for unread emails only

    Returns:
        List of emails
    """
    query = select(Email).where(Email.user_id == user_id)

    if unread_only:
        query = query.where(Email.is_read == False)

    query = query.order_by(desc(Email.received_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    emails = result.scalars().all()

    return [
        EmailResponse(
            id=email.id,
            message_id=email.message_id,
            subject=email.subject or "",
            sender=email.sender or {},
            summary=email.summary,
            key_points=email.key_points,
            suggested_actions=email.suggested_actions,
            received_at=email.received_at.isoformat(),
            is_read=email.is_read,
            urgency_score=email.urgency_score,
            category=email.category,
        )
        for email in emails
    ]


@router.get("/{email_id}")
async def get_email(
    email_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get single email by ID

    Args:
        email_id: Email database ID
        user_id: User ID from JWT
        db: Database session

    Returns:
        Email details
    """
    result = await db.execute(
        select(Email).where(
            Email.id == email_id,
            Email.user_id == user_id
        )
    )
    email = result.scalars().first()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found"
        )

    return {
        "id": email.id,
        "message_id": email.message_id,
        "subject": email.subject,
        "sender": email.sender,
        "recipients": email.recipients,
        "body_text": email.body_text,
        "body_html": email.body_html,
        "received_at": email.received_at.isoformat(),
        "is_read": email.is_read,
        "has_attachments": email.has_attachments,
        "importance": email.importance,
        "summary": email.summary,
        "key_points": email.key_points,
        "suggested_actions": email.suggested_actions,
        "sentiment": email.sentiment,
        "urgency_score": email.urgency_score,
        "category": email.category,
        "ai_model_used": email.ai_model_used,
        "processing_time_seconds": email.processing_time_seconds,
    }


@router.get("/{email_id}/similar", response_model=List[SimilarEmailResponse])
async def get_similar_emails(
    email_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    n_results: int = Query(default=5, ge=1, le=20)
):
    """
    Find similar emails using semantic search

    Args:
        email_id: Email database ID
        user_id: User ID from JWT
        db: Database session
        n_results: Number of similar emails to return

    Returns:
        List of similar emails
    """
    # Get the email
    result = await db.execute(
        select(Email).where(
            Email.id == email_id,
            Email.user_id == user_id
        )
    )
    email = result.scalars().first()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found"
        )

    # Search for similar emails in vector store
    similar = vector_store.search_similar_emails(
        query_text=f"{email.subject}\n\n{email.body_text or email.body_html or ''}",
        user_id=user_id,
        n_results=n_results + 1  # +1 to exclude the email itself
    )

    # Filter out the current email and format results
    similar_emails = []
    for item in similar:
        if item['email_id'] != email.message_id:
            metadata = item['metadata']
            similar_emails.append(
                SimilarEmailResponse(
                    email_id=item['email_id'],
                    similarity=item['similarity'],
                    subject=metadata.get('subject', ''),
                    sender=metadata.get('sender', ''),
                    preview=item['document'][:200]
                )
            )

    return similar_emails[:n_results]


@router.post("/search")
async def search_emails(
    query: str,
    user_id: int = Depends(get_current_user_id),
    n_results: int = Query(default=10, ge=1, le=50)
):
    """
    Semantic search across all emails

    Args:
        query: Natural language search query
        user_id: User ID from JWT
        n_results: Number of results to return

    Returns:
        List of matching emails
    """
    # Search in vector store
    results = vector_store.search_similar_emails(
        query_text=query,
        user_id=user_id,
        n_results=n_results
    )

    return {
        "query": query,
        "results": [
            {
                "email_id": item['email_id'],
                "similarity": item['similarity'],
                "subject": item['metadata'].get('subject', ''),
                "sender": item['metadata'].get('sender', ''),
                "received_at": item['metadata'].get('received_at', ''),
                "preview": item['document'][:200]
            }
            for item in results
        ]
    }


@router.get("/{email_id}/context")
async def get_email_context(
    email_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get contextual information for an email (similar emails, sender history)

    Args:
        email_id: Email database ID
        user_id: User ID from JWT
        db: Database session

    Returns:
        Context information
    """
    # Get the email
    result = await db.execute(
        select(Email).where(
            Email.id == email_id,
            Email.user_id == user_id
        )
    )
    email = result.scalars().first()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found"
        )

    # Get context from vector store
    context = vector_store.get_email_context(
        email_id=email.message_id,
        user_id=user_id,
        n_similar=3
    )

    return {
        "email_id": email.message_id,
        "similar_emails": context.get("similar_emails", []),
        "sender_history": context.get("sender_emails", [])
    }
