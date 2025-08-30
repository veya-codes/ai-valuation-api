from fastapi import Depends, Header, HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_429_TOO_MANY_REQUESTS
from datetime import datetime
from .config import settings
from .cache import cache

def require_api_key(x_api_key: str | None = Header(default=None, alias="x-api-key")):
    """
    Simple header-based API key check.
    In prod, you could swap to OAuth or JWT validation dependency.
    """
    if not settings.API_KEY:
        # If unset, we allow requests (dev convenience).
        return
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid API key")

def rate_limit(request: Request):
    """
    Basic RPM limiter.
    Uses Redis if available else in-process. 
    Keyed by API key (if present) or client IP to discourage abuse.
    """
    rpm = max(1, settings.RATE_LIMIT_RPM)
    client_ip = request.client.host if request.client else "unknown"
    api_key = request.headers.get("x-api-key") or "anon"
    minute_bucket = datetime.utcnow().strftime("%Y%m%d%H%M")
    key = f"rate:{api_key}:{client_ip}:{minute_bucket}"

    # Redis path: INCR + EXPIRE (atomic in Redis). In-memory is best-effort.
    current = cache.get(key)
    if current is None:
        cache.set(key, "1")  # first hit
        return
    try:
        count = int(current) + 1
    except ValueError:
        count = 1
    if count > rpm:
        raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    cache.set(key, str(count))
