import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Define metrics (names follow Prometheus conventions)
REQ_COUNT = Counter("http_requests_total", "Total HTTP requests", ["path","method","code"])
REQ_LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["path","method"])

class PromMiddleware(BaseHTTPMiddleware):
    """
    Measures latency and counts requests. Cheap and useful in prod.
    """
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start

        # Use raw path to prevent label explosion in a real app (consider templating)
        path = request.url.path
        method = request.method
        code = str(response.status_code)

        REQ_COUNT.labels(path=path, method=method, code=code).inc()
        REQ_LATENCY.labels(path=path, method=method).observe(elapsed)
        return response

async def metrics_endpoint(request: Request):
    """
    GET /v1/metrics — scraped by Prometheus.
    """
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
