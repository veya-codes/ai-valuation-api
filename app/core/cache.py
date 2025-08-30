from typing import Any
from cachetools import TTLCache
from .config import settings

# In-process cache for quick wins and local dev.
_local_cache = TTLCache(maxsize=4096, ttl=settings.CACHE_TTL_SECONDS)

try:
    import redis  # Optional dependency
except Exception:
    redis = None

class Cache:
    """
    Thin abstraction over Redis/in-memory so swapping is one flag away.
    """
    def __init__(self):
        self.backend = None
        if settings.USE_REDIS and redis is not None:
            self.backend = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    def get(self, key: str) -> Any | None:
        if self.backend:
            return self.backend.get(key)
        return _local_cache.get(key)

    def set(self, key: str, value: str) -> None:
        if self.backend:
            self.backend.setex(key, settings.CACHE_TTL_SECONDS, value)
        else:
            _local_cache[key] = value

cache = Cache()
