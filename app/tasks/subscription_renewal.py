"""Celery tasks for webhook subscription renewal"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from app.tasks.celery_app import celery_app
from app.db.models import User
from app.db.database import async_session_factory
from app.services.webhook_service import WebhookService


@celery_app.task
def renew_expiring_subscriptions():
    """
    Scheduled task to renew webhook subscriptions expiring soon

    Runs every hour via Celery Beat
    Renews subscriptions expiring within 24 hours
    """
    try:
        asyncio.run(_renew_expiring_subscriptions_async())
    except Exception as e:
        print(f"Error renewing subscriptions: {e}")


async def _renew_expiring_subscriptions_async():
    """
    Async helper for subscription renewal

    Finds all users with subscriptions expiring in <24 hours and renews them
    """
    async with async_session_factory() as db:
        # Find users with expiring subscriptions
        expiry_threshold = datetime.utcnow() + timedelta(hours=24)

        result = await db.execute(
            select(User).where(
                User.webhook_subscription_id.isnot(None),
                User.webhook_expires_at < expiry_threshold
            )
        )
        users = result.scalars().all()

        print(f"Found {len(users)} subscriptions to renew")

        webhook_service = WebhookService()
        renewed_count = 0
        failed_count = 0

        for user in users:
            try:
                subscription = await webhook_service.renew_subscription_for_user(
                    db=db,
                    user_id=user.id
                )

                if subscription:
                    print(f"Renewed subscription for user {user.id} ({user.email})")
                    renewed_count += 1
                else:
                    print(f"Failed to renew subscription for user {user.id}")
                    failed_count += 1

            except Exception as e:
                print(f"Error renewing subscription for user {user.id}: {e}")
                failed_count += 1

        print(f"Subscription renewal complete: {renewed_count} renewed, {failed_count} failed")


@celery_app.task
def renew_subscription_for_user(user_id: int):
    """
    Manually renew subscription for a specific user

    Args:
        user_id: User ID
    """
    try:
        asyncio.run(_renew_user_subscription_async(user_id))
    except Exception as e:
        print(f"Error renewing subscription for user {user_id}: {e}")


async def _renew_user_subscription_async(user_id: int):
    """
    Async helper for single user subscription renewal

    Args:
        user_id: User ID
    """
    async with async_session_factory() as db:
        webhook_service = WebhookService()

        subscription = await webhook_service.renew_subscription_for_user(
            db=db,
            user_id=user_id
        )

        if subscription:
            print(f"Successfully renewed subscription for user {user_id}")
        else:
            print(f"Failed to renew subscription for user {user_id}")
