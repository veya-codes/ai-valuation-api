import json
import re
from statistics import median

from fastapi import HTTPException

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

    async def identify_property(self, raw_address: str) -> list[dict]:
        """Use OpenAI to disambiguate the provided address.

        Returns a list of candidate addresses with confidence scores. If the
        OpenAI client is unavailable, the raw address is returned with high
        confidence so the service can continue operating offline.
        """
        # Basic local parsing for unit indicators before falling back to OpenAI
        # Examples: "123 Main St #5", "123 Main St Unit 5", "5, 123 Main St"
        unit_indicator = False
        cleaned_address = raw_address

        # Pattern: leading number followed by a comma (unit at start)
        leading_match = re.match(r"^\s*\d+\s*,\s*(.+)$", raw_address)
        if leading_match:
            cleaned_address = leading_match.group(1).strip()
            unit_indicator = True

        # Patterns like "Unit 5" or "#5" anywhere in the string
        if not unit_indicator and re.search(r"\b(unit|apt|suite)\s*\w+", raw_address, re.IGNORECASE):
            cleaned_address = re.sub(r"\b(unit|apt|suite)\s*\w+", "", raw_address, flags=re.IGNORECASE)
            unit_indicator = True
        if not unit_indicator and "#" in raw_address:
            cleaned_address = re.sub(r"#\s*\w+", "", raw_address).strip()
            unit_indicator = True

        if unit_indicator:
            cleaned_address = cleaned_address.strip().strip(",")
            cleaned_address = re.sub(r"\s+,", ",", cleaned_address)
            cleaned_address = re.sub(r"\s{2,}", " ", cleaned_address)
            return [{"address": cleaned_address, "property_type": "condo", "confidence": 1.0}]

        api_key = settings.OPENAI_API_KEY
        model = settings.OPENAI_MODEL

        try:
            if not api_key or not model:
                raise RuntimeError("OpenAI settings missing")
            import openai  # type: ignore
            openai.api_key = api_key
            prompt = (
                "You are an address parser. Given an input address, return JSON "
                "with a 'candidates' list, each item having 'address' and "
                "'confidence' (0-1)."
                f" Input: {raw_address!r}"
            )
            completion = await openai.ChatCompletion.acreate(
                model=model,
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            content = completion["choices"][0]["message"]["content"]
            data = json.loads(content)
            candidates = data.get("candidates", [])
            if not isinstance(candidates, list):
                candidates = []
            return candidates
        except Exception:
            # Fallback: treat the raw address as a single high-confidence candidate
            return [{"address": raw_address, "confidence": 1.0}]

    async def value_address(self, raw_address: str) -> tuple[dict, bool, str]:
        candidates = await self.identify_property(raw_address)
        if len(candidates) != 1 or candidates[0].get("confidence", 0) < 0.7:
            raise HTTPException(
                status_code=400,
                detail="Unable to confidently identify the property address; please provide more details.",
            )

        confirmed_address = candidates[0]["address"]
        property_type_hint = candidates[0].get("property_type")
        addr_norm = normalize_address(confirmed_address)
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

        # Basic heuristic: presence of unit indicators implies a condo/apt.
        # If identify_property hinted at a property type, use it.
        property_type = (
            property_type_hint
            or (
                "condo"
                if any(token in addr_norm for token in ("#", "unit", "apt", "suite"))
                else "house"
            )
        )

        # Shared feature dictionary passed to any model
        features = {
            "address_norm": addr_norm,
            "lat": geo.point.lat,
            "lon": geo.point.lon,
            "area_name": geo.area.name,
            "area_code": geo.area.code,
            "city": geo.city,
            "province": geo.province,
            "property_type": property_type,
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
            "address": confirmed_address,
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
