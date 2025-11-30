"""Webhook subscription management service"""
import secrets
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import User
from app.services.graph_client import GraphClient
from app.services.oauth_service import OAuthService


class WebhookService:
    """Service for managing Microsoft Graph webhook subscriptions"""

    def __init__(self):
        self.oauth_service = OAuthService()

    async def create_subscription_for_user(
        self,
        db: AsyncSession,
        user_id: int,
        notification_url: str
    ) -> Optional[dict]:
        """
        Create webhook subscription for user's inbox

        Args:
            db: Database session
            user_id: User ID
            notification_url: Public webhook callback URL

        Returns:
            Subscription data or None on failure
        """
        # Get valid access token
        access_token = await self.oauth_service.get_valid_access_token(db, user_id)
        if not access_token:
            print(f"Failed to get access token for user {user_id}")
            return None

        # Create Graph client
        graph_client = GraphClient(access_token)

        # Generate client state for security
        client_state = secrets.token_urlsafe(32)

        # Create subscription
        subscription = await graph_client.create_webhook_subscription(
            notification_url=notification_url,
            resource="me/mailFolders/inbox/messages",
            change_type="created",
            expiration_minutes=4230,  # ~3 days
            client_state=client_state
        )

        if not subscription:
            print(f"Failed to create subscription for user {user_id}")
            return None

        # Store subscription info in user record
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                webhook_subscription_id=subscription["id"],
                webhook_expires_at=datetime.fromisoformat(
                    subscription["expirationDateTime"].replace("Z", "+00:00")
                )
            )
        )
        await db.commit()

        return subscription

    async def renew_subscription_for_user(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Optional[dict]:
        """
        Renew existing webhook subscription for user

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Updated subscription data or None on failure
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

        if not user or not user.webhook_subscription_id:
            print(f"No subscription found for user {user_id}")
            return None

        # Get valid access token
        access_token = await self.oauth_service.get_valid_access_token(db, user_id)
        if not access_token:
            print(f"Failed to get access token for user {user_id}")
            return None

        # Create Graph client
        graph_client = GraphClient(access_token)

        # Renew subscription
        subscription = await graph_client.renew_webhook_subscription(
            subscription_id=user.webhook_subscription_id,
            expiration_minutes=4230
        )

        if not subscription:
            print(f"Failed to renew subscription for user {user_id}")
            return None

        # Update expiration in user record
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                webhook_expires_at=datetime.fromisoformat(
                    subscription["expirationDateTime"].replace("Z", "+00:00")
                )
            )
        )
        await db.commit()

        return subscription

    async def delete_subscription_for_user(
        self,
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """
        Delete webhook subscription for user

        Args:
            db: Database session
            user_id: User ID

        Returns:
            True if successful
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

        if not user or not user.webhook_subscription_id:
            return False

        # Get valid access token
        access_token = await self.oauth_service.get_valid_access_token(db, user_id)
        if not access_token:
            return False

        # Create Graph client
        graph_client = GraphClient(access_token)

        # Delete subscription
        success = await graph_client.delete_webhook_subscription(
            user.webhook_subscription_id
        )

        if success:
            # Clear subscription info
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    webhook_subscription_id=None,
                    webhook_expires_at=None
                )
            )
            await db.commit()

        return success

    async def get_subscription_status(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Optional[dict]:
        """
        Get current webhook subscription status for user

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Subscription status data
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

        if not user:
            return None

        if not user.webhook_subscription_id:
            return {
                "subscribed": False,
                "subscription_id": None,
                "expires_at": None
            }

        # Get valid access token
        access_token = await self.oauth_service.get_valid_access_token(db, user_id)
        if not access_token:
            return {
                "subscribed": True,
                "subscription_id": user.webhook_subscription_id,
                "expires_at": user.webhook_expires_at,
                "status": "token_expired"
            }

        # Create Graph client
        graph_client = GraphClient(access_token)

        # Get subscription details from Graph
        subscription = await graph_client.get_webhook_subscription(
            user.webhook_subscription_id
        )

        if not subscription:
            return {
                "subscribed": True,
                "subscription_id": user.webhook_subscription_id,
                "expires_at": user.webhook_expires_at,
                "status": "not_found_in_graph"
            }

        return {
            "subscribed": True,
            "subscription_id": subscription["id"],
            "resource": subscription.get("resource"),
            "change_type": subscription.get("changeType"),
            "expires_at": subscription.get("expirationDateTime"),
            "status": "active"
        }
