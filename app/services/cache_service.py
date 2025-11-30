"""Redis caching service for AI responses and Graph API data"""
import json
import hashlib
from typing import Optional, Any
from redis import Redis
from app.core.config import settings

# Redis client instance
redis_client = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
)


class CacheService:
    """Service for caching data in Redis"""

    @staticmethod
    def _generate_key(prefix: str, identifier: str) -> str:
        """
        Generate a cache key with prefix

        Args:
            prefix: Cache key prefix (e.g., 'ai_summary', 'graph_api')
            identifier: Unique identifier for the cached item

        Returns:
            Formatted cache key
        """
        return f"{prefix}:{identifier}"

    @staticmethod
    def _hash_content(content: str) -> str:
        """
        Generate SHA256 hash of content for cache key

        Args:
            content: Content to hash

        Returns:
            Hex digest of SHA256 hash
        """
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def get(key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            value = redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None

    @staticmethod
    def set(key: str, value: Any, ttl: int) -> bool:
        """
        Set value in cache with TTL

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
            return False

    @staticmethod
    def delete(key: str) -> bool:
        """
        Delete value from cache

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Cache delete error: {e}")
            return False

    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """
        Delete all keys matching pattern

        Args:
            pattern: Redis key pattern (e.g., 'ai_summary:*')

        Returns:
            Number of keys deleted
        """
        try:
            keys = redis_client.keys(pattern)
            if keys:
                return redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Cache delete pattern error: {e}")
            return 0

    # AI Response Caching Methods
    @staticmethod
    def get_ai_summary(email_content_hash: str) -> Optional[str]:
        """Get cached AI summary by email content hash"""
        key = CacheService._generate_key("ai_summary", email_content_hash)
        return CacheService.get(key)

    @staticmethod
    def set_ai_summary(email_content_hash: str, summary: str) -> bool:
        """Cache AI summary for email content"""
        key = CacheService._generate_key("ai_summary", email_content_hash)
        return CacheService.set(key, summary, settings.CACHE_TTL_AI_RESPONSES)

    @staticmethod
    def get_ai_actions(email_content_hash: str) -> Optional[list]:
        """Get cached AI action recommendations"""
        key = CacheService._generate_key("ai_actions", email_content_hash)
        return CacheService.get(key)

    @staticmethod
    def set_ai_actions(email_content_hash: str, actions: list) -> bool:
        """Cache AI action recommendations"""
        key = CacheService._generate_key("ai_actions", email_content_hash)
        return CacheService.set(key, actions, settings.CACHE_TTL_AI_RESPONSES)

    @staticmethod
    def get_ai_reply(email_content_hash: str) -> Optional[str]:
        """Get cached AI reply suggestion"""
        key = CacheService._generate_key("ai_reply", email_content_hash)
        return CacheService.get(key)

    @staticmethod
    def set_ai_reply(email_content_hash: str, reply: str) -> bool:
        """Cache AI reply suggestion"""
        key = CacheService._generate_key("ai_reply", email_content_hash)
        return CacheService.set(key, reply, settings.CACHE_TTL_AI_RESPONSES)

    # Graph API Caching Methods
    @staticmethod
    def get_graph_response(endpoint: str) -> Optional[Any]:
        """Get cached Microsoft Graph API response"""
        endpoint_hash = CacheService._hash_content(endpoint)
        key = CacheService._generate_key("graph_api", endpoint_hash)
        return CacheService.get(key)

    @staticmethod
    def set_graph_response(endpoint: str, response: Any) -> bool:
        """Cache Microsoft Graph API response"""
        endpoint_hash = CacheService._hash_content(endpoint)
        key = CacheService._generate_key("graph_api", endpoint_hash)
        return CacheService.set(key, response, settings.CACHE_TTL_GRAPH_API)

    @staticmethod
    def invalidate_user_cache(user_id: int) -> int:
        """Invalidate all cache entries for a specific user"""
        patterns = [
            f"ai_summary:*user_{user_id}*",
            f"ai_actions:*user_{user_id}*",
            f"ai_reply:*user_{user_id}*",
            f"graph_api:*user_{user_id}*",
        ]
        total_deleted = 0
        for pattern in patterns:
            total_deleted += CacheService.delete_pattern(pattern)
        return total_deleted
