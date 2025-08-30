import json
from statistics import median
from ..core.config import settings
from ..core.cache import cache
from ..core.utils import normalize_address, weak_etag
from ..data.geocode_client import geocode_client
from ..data.comps_client import comps_client
from ..data.trends_client import trends_client
from ..models.mock_model import MockModel
from ..models.ml_model import SklearnRegressor
from ..models.llm_model import LLMModel
from ..models.openai_model import OpenAIModel

class ValuationService:
    """
    Orchestrates:
      address → geocode → comps + trends → engineered features → model.predict
    Handles caching and ETag generation for speed and CDN-friendliness.
    """
    def __init__(self):
        # Pick model provider based on env
        provider = settings.MODEL_PROVIDER
        if provider == "ml":
            try:
                self.model = SklearnRegressor(settings.MODEL_PATH)
            except Exception:
                # Fail gracefully to mock if model missing
                self.model = MockModel()
        elif provider == "llm":
            self.model = LLMModel()
        elif provider == "openai":
            assert settings.OPENAI_API_KEY, "OPENAI_API_KEY is required for OpenAI model"
            self.model = OpenAIModel()
        else:
            self.model = MockModel()

        # Data adapters (mock or HTTP)
        self.geo = geocode_client()
        self.comps = comps_client()
        self.trends = trends_client()

    async def value_address(self, raw_address: str) -> tuple[dict, bool, str]:
        addr_norm = normalize_address(raw_address)
        cache_key = f"valuation:{addr_norm}"
        cached = cache.get(cache_key)
        if cached:
            payload = json.loads(cached)
            etag = weak_etag(json.dumps(payload, separators=(',',':')).encode("utf-8"))
            return payload, True, etag

        # 1) Geocode (address -> point & area)
        geo = await self.geo.resolve(addr_norm)

        # 2) Comps (last 90 days within ~2km)
        comps = await self.comps.recent_sales(
            point=geo.point, radius_km=2.0, max_age_days=90, limit=6
        )
        comps_prices = [c.sale_price for c in comps]
        comps_avg = int(sum(comps_prices)/len(comps_prices)) if comps_prices else None

        # 3) Trends (12 months index for area)
        index12 = await self.trends.price_index(geo.area, months=12)
        # Derive MoM % change from last two points (fallback to ~0)
        trend_mom_pct = 0.0
        if len(index12) >= 2 and index12[-2].index:
            prev, curr = index12[-2].index, index12[-1].index
            trend_mom_pct = (curr - prev) / prev * 100.0

        # Basic feature extraction for model
        beds_m = median([c.beds for c in comps if c.beds is not None]) if comps else 3
        baths_m = median([c.baths for c in comps if c.baths is not None]) if comps else 2
        sqft_m = median([c.living_sqft for c in comps if c.living_sqft is not None]) if comps else 1200

        # Signal quality heuristic: more comps + recent trend ⇒ better
        signal_quality = min(30, (len(comps) * 4) + (abs(trend_mom_pct) // 0.5))

        # Insights (human-friendly and model-agnostic)
        insights = []
        if comps:
            insights.append(f"{len(comps)} comparable sale(s) within ~2km in the last 90 days.")
        if trend_mom_pct != 0:
            direction = "up" if trend_mom_pct > 0 else "down"
            insights.append(f"Local price index is {direction} {abs(trend_mom_pct):.1f}% MoM.")

        # Shared feature dictionary passed to any model
        features = {
            "address_norm": addr_norm,
            "lat": geo.point.lat,
            "lon": geo.point.lon,
            "area_name": geo.area.name,
            "area_code": geo.area.code,
            "city": geo.city,
            "province": geo.province,
            "trend_mom_pct": trend_mom_pct,
            "comps_count": len(comps),
            "comps_avg_price": comps_avg or 0,
            "beds_median": beds_m,
            "baths_median": baths_m,
            "sqft_median": sqft_m,
            "insights": insights,
        }

        # 4) Predict using selected model
        model_out = self.model.predict(features)

        # 5) Assemble API response
        payload = {
            "address": raw_address,
            "currency": settings.DEFAULT_CURRENCY,
            "valuation": model_out["base"],
            "range": {"low": model_out["low"], "high": model_out["high"]},
            "confidence": model_out["confidence"],
            "trend_mom_pct": round(model_out["trend_mom_pct"], 1),
            "comparables_used": model_out["comps"],
            "insights": model_out["insights"],
            "sparkline_index_12m": model_out["sparkline"],
            "factors": model_out["factors"],
            "disclaimer": "This valuation is an estimate and not a financial appraisal.",
            "cached": False,
        }

        # Cache+etag for repeat queries
        cache.set(cache_key, json.dumps(payload, separators=(',',':')))
        etag = weak_etag(json.dumps(payload, separators=(',',':')).encode("utf-8"))
        return payload, False, etag
