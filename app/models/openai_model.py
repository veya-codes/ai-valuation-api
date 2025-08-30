"""OpenAI-backed valuation model."""

from __future__ import annotations

import json
from typing import Any, Dict

from .base import ValuationModel
from ..core.config import settings


class OpenAIModel(ValuationModel):
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Call OpenAI's chat completion API to estimate property valuation.

        Parameters
        ----------
        features: Dict[str, Any]
            Structured feature payload describing the property.

        Returns
        -------
        Dict[str, Any]
            Parsed JSON response from the model containing valuation fields.
        """

        api_key = settings.OPENAI_API_KEY
        model = settings.OPENAI_MODEL

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY missing from settings")
        if not model:
            raise RuntimeError("OPENAI_MODEL missing from settings")

        try:  # Import lazily so the package remains optional for other models
            import openai
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("openai package is required for OpenAIModel") from exc

        openai.api_key = api_key

        prompt = (
            "You are a real estate valuation model. "
            "Respond ONLY with valid JSON containing keys "
            "base, low, high, confidence, trend_mom_pct, comps, insights, "
            "sparkline, and factors. "
            f"The property type is {features.get('property_type')}. "
            f"Use these features: {json.dumps(features)}"
        )

        try:
            completion = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            content = completion["choices"][0]["message"]["content"]
            data = json.loads(content)
        except Exception as exc:  # pragma: no cover - network/JSON issues
            raise RuntimeError("Error invoking OpenAI API or parsing response") from exc

        expected = {
            "base",
            "low",
            "high",
            "confidence",
            "trend_mom_pct",
            "comps",
            "insights",
            "sparkline",
            "factors",
        }
        missing = expected.difference(data)
        if missing:
            raise ValueError(f"Malformed response missing keys: {sorted(missing)}")

        return data
