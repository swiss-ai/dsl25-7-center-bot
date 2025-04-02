import time
import logging
from typing import Dict, Optional, Callable, Any, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from config.settings import settings

logger = logging.getLogger(__name__)

class InMemoryStore:
    """Simple in-memory store for rate limiting."""
    
    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}
    
    def increment(self, key: str, window: int, max_requests: int) -> Tuple[int, bool]:
        """
        Increment the counter for a key.
        
        Args:
            key: The rate limit key
            window: Time window in seconds
            max_requests: Maximum requests allowed in the window
            
        Returns:
            Tuple of (current count, is allowed)
        """
        now = time.time()
        
        # Create or update entry
        if key not in self.store or self.store[key]["reset_at"] <= now:
            self.store[key] = {
                "count": 1,
                "reset_at": now + window,
                "max_requests": max_requests
            }
            return 1, True
        
        # Increment existing entry
        entry = self.store[key]
        entry["count"] += 1
        
        return entry["count"], entry["count"] <= max_requests
    
    def get_window_stats(self, key: str) -> Tuple[int, int, int]:
        """
        Get statistics for the current window.
        
        Args:
            key: The rate limit key
            
        Returns:
            Tuple of (current count, max requests, seconds until reset)
        """
        now = time.time()
        
        if key not in self.store:
            return 0, 0, 0
        
        entry = self.store[key]
        reset_in = max(0, int(entry["reset_at"] - now))
        
        return entry["count"], entry.get("max_requests", 0), reset_in

class RedisStore:
    """Redis-based store for rate limiting."""
    
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
    
    def increment(self, key: str, window: int, max_requests: int) -> Tuple[int, bool]:
        """
        Increment the counter for a key using Redis.
        
        Args:
            key: The rate limit key
            window: Time window in seconds
            max_requests: Maximum requests allowed in the window
            
        Returns:
            Tuple of (current count, is allowed)
        """
        pipeline = self.redis.pipeline()
        
        # Check if key exists
        pipeline.exists(key)
        # Increment counter
        pipeline.incr(key)
        # Get TTL
        pipeline.ttl(key)
        
        results = pipeline.execute()
        key_exists, current_count, ttl = results
        
        # Set expiry if key is new
        if not key_exists:
            self.redis.expire(key, window)
            # Store max_requests as metadata with suffix
            self.redis.set(f"{key}:max", max_requests, ex=window)
        
        return current_count, current_count <= max_requests
    
    def get_window_stats(self, key: str) -> Tuple[int, int, int]:
        """
        Get statistics for the current window from Redis.
        
        Args:
            key: The rate limit key
            
        Returns:
            Tuple of (current count, max requests, seconds until reset)
        """
        pipeline = self.redis.pipeline()
        pipeline.get(key)
        pipeline.get(f"{key}:max")
        pipeline.ttl(key)
        
        results = pipeline.execute()
        count_str, max_str, ttl = results
        
        count = int(count_str) if count_str else 0
        max_requests = int(max_str) if max_str else 0
        reset_in = max(0, ttl)
        
        return count, max_requests, reset_in

class RateLimiter(BaseHTTPMiddleware):
    """Rate limiting middleware for FastAPI."""
    
    def __init__(
        self, 
        app,
        redis_url: Optional[str] = None,
        window: int = 60,  # 1 minute window
        max_requests: int = 100,
        identifier_key: Callable[[Request], str] = None
    ):
        super().__init__(app)
        
        # Set up storage backend
        if redis_url and REDIS_AVAILABLE:
            self.store = RedisStore(redis_url)
            logger.info("Using Redis for rate limiting")
        else:
            self.store = InMemoryStore()
            logger.info("Using in-memory store for rate limiting")
        
        self.window = window
        self.max_requests = max_requests
        self.identifier_key = identifier_key or self._default_identifier
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request and apply rate limiting."""
        # Skip rate limiting if disabled
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Get identifier for this request
        identifier = await self.identifier_key(request)
        rate_limit_key = f"ratelimit:{identifier}"
        
        # Check rate limit
        current, allowed = self.store.increment(
            rate_limit_key,
            self.window,
            self.max_requests
        )
        
        # Add rate limit headers
        response = await call_next(request) if allowed else Response(
            content="Rate limit exceeded",
            status_code=HTTP_429_TOO_MANY_REQUESTS
        )
        
        # Get window stats for headers
        count, limit, reset_in = self.store.get_window_stats(rate_limit_key)
        
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.max_requests - count))
        response.headers["X-RateLimit-Reset"] = str(reset_in)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {identifier}")
        
        return response
    
    @staticmethod
    async def _default_identifier(request: Request) -> str:
        """Default function to identify the client."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        return f"{ip}:{request.url.path}"