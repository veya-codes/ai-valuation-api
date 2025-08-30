from typing import Dict, Any
from .base import ValuationModel
from ..core.utils import fnv1a_32, seeded_rand, money_band, sparkline

class MockModel(ValuationModel):
    """
    Deterministic placeholder model. Uses the address seed and lightweight
    inputs (like number of comps, last month trend) to produce plausible outputs.
    """
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        address = features.get("address_norm", "unknown")
        seed = fnv1a_32(address)

        # Base price driven by seed, nudged by comps average & trend
        base_seed = int(350_000 + seeded_rand(seed,1)[0] * 1_850_000)
        comps_avg = int(features.get("comps_avg_price", base_seed))
        trend_pct = float(features.get("trend_mom_pct", 0.0))

        # Blend base with comps and a bit of trend
        blended = int(0.6*base_seed + 0.35*comps_avg * (1 + trend_pct/100.0) + 0.05*base_seed)

        low, high = money_band(blended, seed)
        confidence = int(60 + min(30, max(0, features.get("signal_quality", 0))))  # 60–90
        comps = int(features.get("comps_count", 4))
        insights = features.get("insights", [])
        if not insights:
            insights = ["Comparable activity supports the estimate." if comps >=4 else "Limited recent comps in radius."]

        return {
            "base": blended,
            "low": low,
            "high": high,
            "confidence": confidence,
            "trend_mom_pct": round(trend_pct, 1),
            "comps": comps,
            "insights": insights,
            "sparkline": sparkline(seed),
            "factors": {
                "comps_weight": 0.45,
                "trend_weight": 0.20,
                "locality_weight": 0.20,
                "property_weight": 0.15,
            }
        }
