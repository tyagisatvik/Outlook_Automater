"""OAuth 2.0 service for Microsoft authentication and token management"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import msal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token, create_access_token
from app.db.models import User


class OAuthService:
    """Service for handling Microsoft OAuth 2.0 flow"""

    SCOPES = ["User.Read", "Mail.Read", "Mail.ReadWrite", "MailboxSettings.Read"]
    AUTHORITY = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}"

    def __init__(self):
        """Initialize MSAL confidential client for OAuth flow"""
        self.msal_app = msal.ConfidentialClientApplication(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
            authority=self.AUTHORITY,
        )

    def get_authorization_url(self, state: str) -> str:
        """
        Get Microsoft OAuth authorization URL

        Args:
            state: Random state string for CSRF protection

        Returns:
            Authorization URL for redirect
        """
        auth_url = self.msal_app.get_authorization_request_url(
            scopes=self.SCOPES,
            state=state,
            redirect_uri=settings.MICROSOFT_REDIRECT_URI,
        )
        return auth_url

    async def exchange_code_for_tokens(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Exchange authorization code for access and refresh tokens

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in
        """
        try:
            result = self.msal_app.acquire_token_by_authorization_code(
                code=code,
                scopes=self.SCOPES,
                redirect_uri=settings.MICROSOFT_REDIRECT_URI,
            )

            if "access_token" in result:
                return result
            else:
                error = result.get("error_description", "Unknown error")
                print(f"Token exchange error: {error}")
                return None

        except Exception as e:
            print(f"Token exchange exception: {e}")
            return None

    async def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh access token using refresh token

        Args:
            refresh_token: Valid refresh token

        Returns:
            New token response with access_token
        """
        try:
            result = self.msal_app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=self.SCOPES,
            )

            if "access_token" in result:
                return result
            else:
                error = result.get("error_description", "Token refresh failed")
                print(f"Token refresh error: {error}")
                return None

        except Exception as e:
            print(f"Token refresh exception: {e}")
            return None

    async def get_user_info_from_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from Microsoft Graph using access token

        Args:
            access_token: Valid access token

        Returns:
            User profile data (id, email, displayName)
        """
        from app.services.graph_client import GraphClient

        client = GraphClient(access_token)
        return await client.get_user_profile()

    async def store_user_tokens(
        self,
        db: AsyncSession,
        microsoft_user_id: str,
        email: str,
        name: str,
        access_token: str,
        refresh_token: str,
        expires_in: int
    ) -> User:
        """
        Store or update user with encrypted OAuth tokens

        Args:
            db: Database session
            microsoft_user_id: Microsoft user ID
            email: User email
            name: User display name
            access_token: Microsoft Graph access token
            refresh_token: Microsoft Graph refresh token
            expires_in: Token expiration time in seconds

        Returns:
            User database object
        """
        # Check if user exists
        result = await db.execute(
            select(User).where(User.microsoft_user_id == microsoft_user_id)
        )
        user = result.scalars().first()

        # Encrypt tokens
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None

        # Calculate expiration
        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        if user:
            # Update existing user
            user.email = email
            user.name = name
            user.access_token_encrypted = encrypted_access
            user.refresh_token_encrypted = encrypted_refresh
            user.token_expires_at = token_expires_at
            user.last_login = datetime.utcnow()
        else:
            # Create new user
            user = User(
                email=email,
                name=name,
                microsoft_user_id=microsoft_user_id,
                access_token_encrypted=encrypted_access,
                refresh_token_encrypted=encrypted_refresh,
                token_expires_at=token_expires_at,
                last_login=datetime.utcnow(),
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)

        return user

    async def get_valid_access_token(self, db: AsyncSession, user_id: int) -> Optional[str]:
        """
        Get valid access token for user, refreshing if necessary

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Valid access token or None
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

        if not user:
            return None

        # Check if token is expired or about to expire (5 min buffer)
        now = datetime.utcnow()
        expires_soon = user.token_expires_at - timedelta(minutes=5)

        if now >= expires_soon:
            # Token expired, refresh it
            if not user.refresh_token_encrypted:
                return None

            refresh_token = decrypt_token(user.refresh_token_encrypted)
            token_response = await self.refresh_access_token(refresh_token)

            if not token_response:
                return None

            # Update user tokens
            user.access_token_encrypted = encrypt_token(token_response["access_token"])
            if "refresh_token" in token_response:
                user.refresh_token_encrypted = encrypt_token(token_response["refresh_token"])
            user.token_expires_at = datetime.utcnow() + timedelta(seconds=token_response["expires_in"])

            await db.commit()
            await db.refresh(user)

            return token_response["access_token"]

        # Token still valid
        return decrypt_token(user.access_token_encrypted)

    def create_app_jwt(self, user: User) -> str:
        """
        Create JWT for application authentication

        Args:
            user: User object

        Returns:
            JWT token
        """
        return create_access_token(
            data={
                "user_id": user.id,
                "email": user.email,
                "microsoft_user_id": user.microsoft_user_id,
            },
            expires_delta=timedelta(days=7)
        )
