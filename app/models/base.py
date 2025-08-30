from typing import Protocol, Dict, Any

class ValuationModel(Protocol):
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a payload with keys:
        base, low, high, confidence, trend_mom_pct, comps, insights, sparkline, factors.
        """
        ...
