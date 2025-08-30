# Illustrative example if/when you wire a real LLM:
# Requires OPENAI_API_KEY in env and openai package (or httpx against your own model server).
# Not used by default.

from .base import ValuationModel
from ..core.config import settings
import os

class OpenAIModel(ValuationModel):
    def predict(self, address: str) -> dict:
        # You would combine upstream signals (comps, trends, features)
        # and prompt the model to produce a structured JSON response.
        # For brevity, we return a stub here; keep the same keys.
        return {
            "base": 950_000,
            "low": 900_000,
            "high": 1_000_000,
            "confidence": 78,
            "trend_mom_pct": 0.9,
            "comps": 5,
            "insights": [
                "Recent comparable within 0.5km at ~960k supports the estimate.",
                "Market momentum mildly positive over the past month."
            ],
            "sparkline": [48,50,51,52,53,55,56,57,58,59,60,61],
            "factors": {
                "comps_weight": 0.35,
                "trend_weight": 0.25,
                "locality_weight": 0.20,
                "property_weight": 0.20,
            },
        }
