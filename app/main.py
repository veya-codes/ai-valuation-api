from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

# Routers
from .routers.valuation import router as valuation_router

# Core modules
from .core.config import settings
from .core.logging import configure_logging, CorrelationIdMiddleware
from .core.metrics import PromMiddleware, metrics_endpoint

def create_app() -> FastAPI:
    """
    App factory so tests and ASGI servers can instantiate cleanly.
    """
    configure_logging()  # Set up JSON logs + correlation-id filter

    app = FastAPI(
        title="AI Property Valuation API",
        version="1.1.0",
        description="Valuation service with data adapters, model pluggability, caching, security, and metrics.",
    )

    # CORS: allow your static site to call the API.
    allow_origins = [o.strip() for o in settings.ALLOW_ORIGINS.split(",")] if settings.ALLOW_ORIGINS else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["ETag","X-Request-Id"],
    )

    # Observability middlewares
    app.add_middleware(CorrelationIdMiddleware)  # Adds/propagates X-Request-Id
    if settings.PROMETHEUS_ENABLED:
        app.add_middleware(PromMiddleware)       # Records req/latency metrics

    # Meta routes
    @app.get("/v1/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    @app.get("/v1/ping", tags=["meta"])
    def ping():
        return {"pong": True}

    if settings.PROMETHEUS_ENABLED:
        # Standard Prometheus scrape endpoint
        app.add_route("/v1/metrics", metrics_endpoint, methods=["GET"])

    # Business routes
    app.include_router(valuation_router, prefix="/v1", tags=["valuation"])

    return app

app = create_app()
