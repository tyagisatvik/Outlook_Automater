"""Celery tasks for email processing"""
import asyncio
from datetime import datetime
from sqlalchemy import select
from app.tasks.celery_app import celery_app
from app.db.models import User, Email
from app.db.database import async_session_factory
from app.services.graph_client import GraphClient
from app.services.oauth_service import OAuthService
from app.services.cache_service import CacheService
from app.services.vector_store import vector_store


@celery_app.task(bind=True, max_retries=3)
def process_email_notification(self, subscription_id: str, message_id: str, change_type: str):
    """
    Process email notification from webhook

    This task is queued when a webhook notification is received.
    It fetches the email, runs AI processing, and stores results.

    Args:
        subscription_id: Webhook subscription ID
        message_id: Email message ID from Graph API
        change_type: Type of change (created, updated, deleted)
    """
    try:
        # Run async processing in sync context
        asyncio.run(_process_email_async(subscription_id, message_id, change_type))
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _process_email_async(subscription_id: str, message_id: str, change_type: str):
    """
    Async helper for email processing

    Args:
        subscription_id: Webhook subscription ID
        message_id: Email message ID
        change_type: Type of change
    """
    async with async_session_factory() as db:
        # Find user by subscription ID
        result = await db.execute(
            select(User).where(User.webhook_subscription_id == subscription_id)
        )
        user = result.scalars().first()

        if not user:
            print(f"User not found for subscription {subscription_id}")
            return

        # Get valid access token
        oauth_service = OAuthService()
        access_token = await oauth_service.get_valid_access_token(db, user.id)

        if not access_token:
            print(f"Failed to get access token for user {user.id}")
            return

        # Fetch email from Graph API
        graph_client = GraphClient(access_token)
        email_data = await graph_client.get_email_by_id(message_id)

        if not email_data:
            print(f"Failed to fetch email {message_id}")
            return

        # Check if email already exists
        result = await db.execute(
            select(Email).where(Email.message_id == message_id)
        )
        existing_email = result.scalars().first()

        if existing_email:
            print(f"Email {message_id} already processed")
            return

        # Extract email data
        subject = email_data.get("subject", "")
        sender = email_data.get("from", {})
        recipients = email_data.get("toRecipients", [])
        body = email_data.get("body", {})
        body_text = body.get("content", "") if body.get("contentType") == "text" else ""
        body_html = body.get("content", "") if body.get("contentType") == "html" else ""
        received_at = datetime.fromisoformat(
            email_data.get("receivedDateTime", "").replace("Z", "+00:00")
        )
        is_read = email_data.get("isRead", False)
        has_attachments = email_data.get("hasAttachments", False)
        importance = email_data.get("importance", "normal")
        conversation_id = email_data.get("conversationId", "")

        # Generate content hash for caching
        content_hash = CacheService._hash_content(f"{subject}:{body_text}")

        # Check cache for AI summary
        cached_summary = CacheService.get_ai_summary(content_hash)
        cached_actions = CacheService.get_ai_actions(content_hash)

        if cached_summary and cached_actions:
            # Use cached AI responses
            summary = cached_summary
            suggested_actions = cached_actions
            ai_model_used = "cached"
            processing_time = 0.0
        else:
            # Run AI processing
            from app.services.ai_service import AIService

            start_time = datetime.utcnow()
            ai_service = AIService()

            # Process email with AI (parallel)
            summary, suggested_actions = await ai_service.process_email(
                subject=subject,
                sender=sender.get("emailAddress", {}).get("address", ""),
                body=body_text or body_html,
                received_at=received_at
            )

            processing_time = (datetime.utcnow() - start_time).total_seconds()
            ai_model_used = ai_service.last_model_used

            # Cache AI responses
            CacheService.set_ai_summary(content_hash, summary)
            CacheService.set_ai_actions(content_hash, suggested_actions)

        # Extract key points from summary
        key_points = summary.split("\n") if summary else []
        key_points = [p.strip("•- ") for p in key_points if p.strip()]

        # Create email record
        email = Email(
            user_id=user.id,
            message_id=message_id,
            conversation_id=conversation_id,
            subject=subject,
            sender=sender,
            recipients=recipients,
            body_text=body_text,
            body_html=body_html,
            received_at=received_at,
            is_read=is_read,
            has_attachments=has_attachments,
            importance=importance,
            summary=summary,
            key_points=key_points,
            suggested_actions=suggested_actions,
            ai_model_used=ai_model_used,
            processing_time_seconds=processing_time,
            processed_at=datetime.utcnow(),
        )

        db.add(email)
        await db.commit()

        # Add email to vector store for semantic search
        sender_email = sender.get("emailAddress", {}).get("address", "") if sender else ""
        vector_store.add_email(
            email_id=message_id,
            subject=subject,
            body=body_text or body_html,
            sender=sender_email,
            user_id=user.id,
            metadata={
                "conversation_id": conversation_id,
                "received_at": received_at.isoformat(),
                "importance": importance,
            }
        )

        print(f"Successfully processed email {message_id} for user {user.id}")


@celery_app.task
def process_email_batch(user_id: int, max_emails: int = 50):
    """
    Batch process unread emails for a user (for manual/scheduled processing)

    Args:
        user_id: User ID
        max_emails: Maximum number of emails to process
    """
    try:
        asyncio.run(_process_email_batch_async(user_id, max_emails))
    except Exception as e:
        print(f"Error processing email batch for user {user_id}: {e}")


async def _process_email_batch_async(user_id: int, max_emails: int):
    """
    Async helper for batch email processing

    Args:
        user_id: User ID
        max_emails: Maximum number of emails to process
    """
    async with async_session_factory() as db:
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

        if not user:
            print(f"User {user_id} not found")
            return

        # Get access token
        oauth_service = OAuthService()
        access_token = await oauth_service.get_valid_access_token(db, user_id)

        if not access_token:
            print(f"Failed to get access token for user {user_id}")
            return

        # Fetch unread emails
        graph_client = GraphClient(access_token)
        emails = await graph_client.fetch_unread_emails(max_count=max_emails)

        print(f"Found {len(emails)} unread emails for user {user_id}")

        # Process each email
        for email_data in emails:
            message_id = email_data.get("id")

            # Queue individual email processing
            process_email_notification.delay(
                subscription_id=user.webhook_subscription_id or "",
                message_id=message_id,
                change_type="created"
            )
