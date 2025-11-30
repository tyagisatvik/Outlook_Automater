"""Webhook endpoints for Microsoft Graph notifications"""
from typing import List, Optional
from fastapi import APIRouter, Request, Response, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.webhook_service import WebhookService
from app.core.security import get_current_user_id

router = APIRouter()
webhook_service = WebhookService()


class WebhookNotification(BaseModel):
    """Model for Microsoft Graph webhook notification"""
    subscriptionId: str
    clientState: Optional[str] = None
    changeType: str
    resource: str
    subscriptionExpirationDateTime: str
    resourceData: Optional[dict] = None


class WebhookValidationRequest(BaseModel):
    """Model for webhook validation request"""
    validationToken: Optional[str] = None


@router.post("/notifications")
async def receive_webhook_notification(
    request: Request,
    response: Response
):
    """
    Receive webhook notifications from Microsoft Graph

    This endpoint must respond in <3 seconds or Microsoft will cancel the subscription

    Args:
        request: FastAPI request object

    Returns:
        202 Accepted (webhook queued for processing)
    """
    # Get request body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    # Handle validation request (sent when creating subscription)
    if "validationToken" in body:
        validation_token = body["validationToken"]
        # Microsoft requires us to return the token as plain text
        return Response(
            content=validation_token,
            media_type="text/plain",
            status_code=200
        )

    # Handle notification
    notifications = body.get("value", [])

    if not notifications:
        return Response(status_code=202)

    # Queue each notification for processing
    from app.tasks.email_tasks import process_email_notification

    for notification in notifications:
        try:
            # Extract resource ID (message ID)
            resource = notification.get("resource", "")
            # Resource format: "Users/{user_id}/Messages/{message_id}"
            message_id = resource.split("/")[-1] if "/" in resource else None

            if message_id:
                # Queue to Celery for background processing
                process_email_notification.delay(
                    subscription_id=notification.get("subscriptionId"),
                    message_id=message_id,
                    change_type=notification.get("changeType"),
                )

        except Exception as e:
            print(f"Error queuing notification: {e}")
            # Continue processing other notifications

    # Return 202 Accepted immediately (within <100ms)
    return Response(status_code=202)


@router.post("/subscribe")
async def create_subscription(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Create webhook subscription for authenticated user

    Args:
        user_id: User ID from JWT token
        db: Database session

    Returns:
        Subscription details
    """
    # In production, this should be your public HTTPS URL
    # For development, use ngrok or similar tunneling service
    notification_url = f"{settings.WEBHOOK_BASE_URL}/api/webhooks/notifications"

    subscription = await webhook_service.create_subscription_for_user(
        db=db,
        user_id=user_id,
        notification_url=notification_url
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create webhook subscription"
        )

    return {
        "message": "Webhook subscription created successfully",
        "subscription": subscription
    }


@router.post("/renew")
async def renew_subscription(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Renew webhook subscription for authenticated user

    Args:
        user_id: User ID from JWT token
        db: Database session

    Returns:
        Updated subscription details
    """
    subscription = await webhook_service.renew_subscription_for_user(
        db=db,
        user_id=user_id
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to renew webhook subscription"
        )

    return {
        "message": "Webhook subscription renewed successfully",
        "subscription": subscription
    }


@router.delete("/unsubscribe")
async def delete_subscription(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete webhook subscription for authenticated user

    Args:
        user_id: User ID from JWT token
        db: Database session

    Returns:
        Success message
    """
    success = await webhook_service.delete_subscription_for_user(
        db=db,
        user_id=user_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete webhook subscription"
        )

    return {"message": "Webhook subscription deleted successfully"}


@router.get("/status")
async def get_subscription_status(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get webhook subscription status for authenticated user

    Args:
        user_id: User ID from JWT token
        db: Database session

    Returns:
        Subscription status
    """
    status_data = await webhook_service.get_subscription_status(
        db=db,
        user_id=user_id
    )

    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return status_data


# Add WEBHOOK_BASE_URL to settings
from app.core.config import settings
if not hasattr(settings, 'WEBHOOK_BASE_URL'):
    # Fallback for development
    settings.WEBHOOK_BASE_URL = "http://localhost:8000"
