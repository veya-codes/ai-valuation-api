from typing import Dict, Any
import pickle
import numpy as np
from .base import ValuationModel

class SklearnRegressor(ValuationModel):
    """
    Loads a pre-trained sklearn regressor from a pickle file.
    Feature engineering here must match the model's training pipeline.
    """

    def __init__(self, model_path: str):
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)  # e.g., RandomForestRegressor or GradientBoostingRegressor

    def _to_vector(self, features: Dict[str, Any]) -> np.ndarray:
        """
        Convert structured features → numeric vector expected by the model.
        This is just an example; align with your real training.
        """
        return np.array([[
            float(features.get("trend_mom_pct", 0.0)),          # feature 1
            float(features.get("comps_avg_price", 0.0)),         # feature 2
            float(features.get("comps_count", 0)),               # feature 3
            float(features.get("beds_median", 3)),               # feature 4
            float(features.get("baths_median", 2)),              # feature 5
            float(features.get("sqft_median", 1200)),            # feature 6
        ]], dtype="float32")

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        X = self._to_vector(features)
        y = float(self.model.predict(X)[0])  # base valuation

        # Derive band & confidence heuristically
        low = int(y * 0.92)
        high = int(y * 1.08)
        confidence = 70 + min(15, int(max(0, features.get("comps_count", 0))))

        return {
            "base": int(y),
            "low": low,
            "high": high,
            "confidence": min(confidence, 95),
            "trend_mom_pct": round(float(features.get("trend_mom_pct", 0.0)), 1),
            "comps": int(features.get("comps_count", 0)),
            "insights": features.get("insights", []),
            "sparkline": features.get("sparkline", []),
            "factors": {
                "comps_weight": 0.4,
                "trend_weight": 0.25,
                "locality_weight": 0.2,
                "property_weight": 0.15,
            }
        }
