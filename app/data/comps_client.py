from datetime import date, timedelta
from .base import CompsClient, GeoPoint, ComparableSale
from ..core.utils import fnv1a_32, seeded_rand
from ..core.config import settings
import httpx
from typing import List

class MockComps(CompsClient):
    """
    Synthetic comps near a lat/lon. Prices/attributes are plausible but fake.
    """
    async def recent_sales(self, point: GeoPoint, radius_km: float, max_age_days: int, limit: int) -> List[ComparableSale]:
        seed = fnv1a_32(f"{point.lat},{point.lon}")
        out: List[ComparableSale] = []
        today = date.today()
        for i in range(limit):
            # Spread comps across the last `max_age_days` days
            age_days = int(seeded_rand(seed+i,1)[0] * max_age_days)
            sale_dt = today - timedelta(days=age_days)
            # Price around a local base
            base = 350_000 + int(seeded_rand(seed+i*31, 1)[0] * 1_850_000)
            # Distance randomized within radius
            dist = round(seeded_rand(seed+7*i,1)[0] * radius_km, 2)
            beds = 2 + int(seeded_rand(seed+13*i,1)[0] * 4)  # 2..5
            baths = 1 + round(seeded_rand(seed+17*i,1)[0] * 2, 1)  # ~1..3
            sqft = 600 + int(seeded_rand(seed+19*i,1)[0] * 2800)
            property_type = "house" if i % 2 == 0 else "condo"
            out.append(ComparableSale(
                distance_km=dist, sale_price=base, sale_date=sale_dt,
                beds=beds, baths=baths, living_sqft=sqft, property_type=property_type
            ))
        # Sort by proximity (closer first)
        out.sort(key=lambda c: (c.distance_km, -c.sale_date.toordinal()))
        return out

class HttpComps(CompsClient):
    """
    Placeholder client for your comps microservice.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def recent_sales(self, point: GeoPoint, radius_km: float, max_age_days: int, limit: int) -> List[ComparableSale]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{self.base_url}/recent-sales",
                params={"lat": point.lat, "lon": point.lon, "radius_km": radius_km,
                        "max_age_days": max_age_days, "limit": limit}
            )
            r.raise_for_status()
            items = r.json()
            return [
                ComparableSale(
                    distance_km=i["distance_km"],
                    sale_price=i["sale_price"],
                    sale_date=date.fromisoformat(i["sale_date"]),
                    beds=i.get("beds"), baths=i.get("baths"), living_sqft=i.get("living_sqft"),
                    property_type=i.get("property_type")
                ) for i in items
            ]

def comps_client():
    if settings.COMPS_PROVIDER == "http" and settings.COMPS_BASE_URL:
        return HttpComps(settings.COMPS_BASE_URL)
    return MockComps()
