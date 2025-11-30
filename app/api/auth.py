"""OAuth authentication endpoints"""
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.database import get_db
from app.services.oauth_service import OAuthService
from app.core.security import get_current_user_id

router = APIRouter()
oauth_service = OAuthService()

# In-memory state storage (use Redis in production)
_state_store = {}


class TokenResponse(BaseModel):
    """Response model for successful authentication"""
    access_token: str
    token_type: str
    user: dict


@router.get("/login")
async def login():
    """
    Initiate OAuth login flow

    Returns redirect URL to Microsoft login page
    """
    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)
    _state_store[state] = True  # Mark as valid

    # Get authorization URL
    auth_url = oauth_service.get_authorization_url(state)

    return {
        "authorization_url": auth_url,
        "state": state
    }


@router.get("/callback")
async def oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth callback endpoint

    Microsoft redirects here after user authentication

    Args:
        code: Authorization code from Microsoft
        state: State parameter for CSRF protection
        db: Database session

    Returns:
        JWT token for application authentication
    """
    # Validate state
    if state not in _state_store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )

    # Remove used state
    del _state_store[state]

    # Exchange code for tokens
    token_response = await oauth_service.exchange_code_for_tokens(code)

    if not token_response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code for tokens"
        )

    # Get user info from Microsoft
    user_info = await oauth_service.get_user_info_from_token(
        token_response["access_token"]
    )

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user information"
        )

    # Store user and tokens
    user = await oauth_service.store_user_tokens(
        db=db,
        microsoft_user_id=user_info["id"],
        email=user_info["mail"] or user_info["userPrincipalName"],
        name=user_info.get("displayName", ""),
        access_token=token_response["access_token"],
        refresh_token=token_response.get("refresh_token"),
        expires_in=token_response.get("expires_in", 3600),
    )

    # Create our app JWT
    app_token = oauth_service.create_app_jwt(user)

    return TokenResponse(
        access_token=app_token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
        }
    )


@router.get("/me")
async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current authenticated user

    Args:
        user_id: User ID from JWT token
        db: Database session

    Returns:
        User profile information
    """
    from sqlalchemy import select
    from app.db.models import User

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "created_at": user.created_at,
        "last_login": user.last_login,
    }


@router.post("/refresh")
async def refresh_token(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh Microsoft Graph access token

    Args:
        user_id: User ID from JWT token
        db: Database session

    Returns:
        Success message
    """
    access_token = await oauth_service.get_valid_access_token(db, user_id)

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to refresh access token"
        )

    return {"message": "Token refreshed successfully"}


@router.post("/logout")
async def logout(user_id: int = Depends(get_current_user_id)):
    """
    Logout current user

    Note: JWT tokens are stateless, so this just returns success.
    Client should discard the token.

    Args:
        user_id: User ID from JWT token

    Returns:
        Success message
    """
    return {"message": "Logged out successfully"}
