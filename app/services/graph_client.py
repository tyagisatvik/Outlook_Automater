"""Microsoft Graph API client with async support and caching"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx
from app.core.config import settings
from app.services.cache_service import CacheService


class GraphClient:
    """Async Microsoft Graph API client"""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, access_token: str):
        """
        Initialize Graph client with access token

        Args:
            access_token: Valid Microsoft Graph access token
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        use_cache: bool = True,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Make async HTTP request to Graph API with caching

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: Graph API endpoint (e.g., '/me/messages')
            use_cache: Whether to use Redis cache for GET requests
            **kwargs: Additional arguments for httpx request

        Returns:
            JSON response or None on error
        """
        url = f"{self.BASE_URL}{endpoint}"

        # Try cache for GET requests
        if method == "GET" and use_cache:
            cached = CacheService.get_graph_response(url)
            if cached:
                return cached

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.request(
                    method,
                    url,
                    headers=self.headers,
                    **kwargs
                )
                response.raise_for_status()
                data = response.json()

                # Cache successful GET requests
                if method == "GET" and use_cache:
                    CacheService.set_graph_response(url, data)

                return data

            except httpx.HTTPStatusError as e:
                print(f"Graph API HTTP error: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                print(f"Graph API request error: {e}")
                return None

    async def get_user_profile(self, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get user profile information

        Args:
            user_id: User ID or email (None for current user)

        Returns:
            User profile data
        """
        endpoint = f"/users/{user_id}" if user_id else "/me"
        return await self._make_request("GET", endpoint)

    async def fetch_emails(
        self,
        user_id: Optional[str] = None,
        folder: str = "inbox",
        filter_query: Optional[str] = None,
        top: int = 50,
        skip: int = 0,
        order_by: str = "receivedDateTime desc"
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from mailbox

        Args:
            user_id: User ID or email (None for current user)
            folder: Mail folder (inbox, sent, drafts, etc.)
            filter_query: OData filter query
            top: Number of emails to fetch
            skip: Number of emails to skip (pagination)
            order_by: Sort order

        Returns:
            List of email messages
        """
        principal = f"users/{user_id}" if user_id else "me"
        endpoint = f"/{principal}/mailfolders/{folder}/messages"

        params = {
            "$top": top,
            "$skip": skip,
            "$orderby": order_by,
        }

        if filter_query:
            params["$filter"] = filter_query

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        full_endpoint = f"{endpoint}?{query_string}"

        result = await self._make_request("GET", full_endpoint, use_cache=False)
        return result.get("value", []) if result else []

    async def fetch_unread_emails(
        self,
        user_id: Optional[str] = None,
        max_count: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch unread emails

        Args:
            user_id: User ID or email (None for current user)
            max_count: Maximum number of emails to fetch

        Returns:
            List of unread email messages
        """
        return await self.fetch_emails(
            user_id=user_id,
            filter_query="isRead eq false",
            top=max_count
        )

    async def get_email_by_id(
        self,
        message_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch single email by ID

        Args:
            message_id: Message ID
            user_id: User ID or email (None for current user)

        Returns:
            Email message data
        """
        principal = f"users/{user_id}" if user_id else "me"
        endpoint = f"/{principal}/messages/{message_id}"
        return await self._make_request("GET", endpoint, use_cache=False)

    async def mark_as_read(
        self,
        message_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Mark email as read

        Args:
            message_id: Message ID
            user_id: User ID or email (None for current user)

        Returns:
            True if successful
        """
        principal = f"users/{user_id}" if user_id else "me"
        endpoint = f"/{principal}/messages/{message_id}"

        result = await self._make_request(
            "PATCH",
            endpoint,
            use_cache=False,
            json={"isRead": True}
        )
        return result is not None

    async def create_webhook_subscription(
        self,
        notification_url: str,
        resource: str,
        change_type: str = "created",
        expiration_minutes: int = 4230,  # Max 3 days (4320 min), set to 2 days 23 hours
        client_state: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create webhook subscription for email notifications

        Args:
            notification_url: Webhook callback URL
            resource: Resource to monitor (e.g., 'me/mailFolders/inbox/messages')
            change_type: Type of change (created, updated, deleted)
            expiration_minutes: Subscription expiration time in minutes (max 4320)
            client_state: Secret for validating notifications

        Returns:
            Subscription data with ID and expiration
        """
        expiration_datetime = datetime.utcnow() + timedelta(minutes=expiration_minutes)

        payload = {
            "changeType": change_type,
            "notificationUrl": notification_url,
            "resource": resource,
            "expirationDateTime": expiration_datetime.isoformat() + "Z",
            "clientState": client_state
        }

        return await self._make_request(
            "POST",
            "/subscriptions",
            use_cache=False,
            json=payload
        )

    async def renew_webhook_subscription(
        self,
        subscription_id: str,
        expiration_minutes: int = 4230
    ) -> Optional[Dict[str, Any]]:
        """
        Renew existing webhook subscription

        Args:
            subscription_id: Subscription ID to renew
            expiration_minutes: New expiration time in minutes

        Returns:
            Updated subscription data
        """
        expiration_datetime = datetime.utcnow() + timedelta(minutes=expiration_minutes)

        payload = {
            "expirationDateTime": expiration_datetime.isoformat() + "Z"
        }

        return await self._make_request(
            "PATCH",
            f"/subscriptions/{subscription_id}",
            use_cache=False,
            json=payload
        )

    async def delete_webhook_subscription(self, subscription_id: str) -> bool:
        """
        Delete webhook subscription

        Args:
            subscription_id: Subscription ID to delete

        Returns:
            True if successful
        """
        result = await self._make_request(
            "DELETE",
            f"/subscriptions/{subscription_id}",
            use_cache=False
        )
        return result is not None

    async def get_webhook_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """
        Get webhook subscription details

        Args:
            subscription_id: Subscription ID

        Returns:
            Subscription data
        """
        return await self._make_request(
            "GET",
            f"/subscriptions/{subscription_id}",
            use_cache=False
        )
