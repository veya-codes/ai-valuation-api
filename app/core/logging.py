import logging
import json
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Simple JSON formatter for line-oriented logs
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        # Include request id if available
        rid = getattr(record, "request_id", None)
        if rid:
            payload["request_id"] = rid
        return json.dumps(payload)

def configure_logging():
    """
    Replace uvicorn default formatter with JSON so App Service/Azure Monitor
    produce structured logs.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has an X-Request-Id header,
    attaches it to the response and log records.
    """
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        # Make it visible to downstream handlers via state
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
