"""Security utilities for JWT authentication and token encryption"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# HTTP Bearer token scheme for FastAPI
security = HTTPBearer()

# Fernet cipher for encrypting OAuth tokens
# In production, this should be stored securely (env variable, secrets manager)
cipher = Fernet(settings.SECRET_KEY[:44].encode().ljust(44, b'='))


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Payload to encode in the token (typically user_id, email)
        expires_delta: Token expiration time (default: 24 hours)

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm="HS256"
    )

    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT access token

    Args:
        token: JWT token to decode

    Returns:
        Decoded payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def encrypt_token(token: str) -> str:
    """
    Encrypt an OAuth token for secure storage

    Args:
        token: Plain text token to encrypt

    Returns:
        Encrypted token (base64 encoded)
    """
    return cipher.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt an encrypted OAuth token

    Args:
        encrypted_token: Encrypted token to decrypt

    Returns:
        Plain text token
    """
    return cipher.decrypt(encrypted_token.encode()).decode()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int:
    """
    FastAPI dependency to extract and verify current user from JWT token

    Args:
        credentials: HTTP Bearer credentials from request header

    Returns:
        User ID from token

    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    user_id: Optional[int] = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id
