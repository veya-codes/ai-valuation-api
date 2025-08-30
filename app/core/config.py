import os
from pydantic import BaseModel

class Settings(BaseModel):
    # Basic
    ENV: str = os.getenv("ENV", "dev")
    DEFAULT_CURRENCY: str = os.getenv("CURRENCY", "CAD")
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "43200"))

    # Models
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "mock")  # mock | ml | llm
    MODEL_PATH: str = os.getenv("MODEL_PATH", "./model/estimator.pkl")

    # LLM
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Data providers
    GEO_PROVIDER: str = os.getenv("GEO_PROVIDER", "mock")          # mock | http
    GEO_BASE_URL: str | None = os.getenv("GEO_BASE_URL")
    COMPS_PROVIDER: str = os.getenv("COMPS_PROVIDER", "mock")      # mock | http
    COMPS_BASE_URL: str | None = os.getenv("COMPS_BASE_URL")
    TRENDS_PROVIDER: str = os.getenv("TRENDS_PROVIDER", "mock")    # mock | http
    TRENDS_BASE_URL: str | None = os.getenv("TRENDS_BASE_URL")

    # Security
    API_KEY: str | None = os.getenv("API_KEY")
    RATE_LIMIT_RPM: int = int(os.getenv("RATE_LIMIT_RPM", "60"))

    # CORS
    ALLOW_ORIGINS: str = os.getenv("ALLOW_ORIGINS", "*")

    # Cache
    USE_REDIS: bool = os.getenv("USE_REDIS", "false").lower() == "true"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Metrics
    PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"

settings = Settings()
