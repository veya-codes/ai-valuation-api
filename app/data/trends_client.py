from datetime import date
from typing import List
from .base import TrendsClient, GeoArea, AreaTrendPoint
from ..core.utils import fnv1a_32, seeded_rand
from ..core.config import settings
import httpx

class MockTrends(TrendsClient):
    """
    Synthetic price index resembling a smoothed series over N months.
    """
    async def price_index(self, area: GeoArea, months: int = 12) -> List[AreaTrendPoint]:
        seed = fnv1a_32(area.name + (area.code or ""))
        # Start around 100 and drift a little
        idx = 100.0 + seeded_rand(seed,1)[0] * 8.0
        out: List[AreaTrendPoint] = []
        today = date.today().replace(day=1)
        for i in range(months, 0, -1):
            # Month-by-month drift +/- 1.5% with some noise
            drift = (seeded_rand(seed+i,1)[0] - 0.5) * 3.0
            idx *= (1.0 + drift/100.0)
            month_date = (today.replace(day=1)).fromordinal(today.toordinal())  # safe copy
            # compute (today - i months)
            year = month_date.year + (month_date.month - i - 1) // 12
            month = (month_date.month - i - 1) % 12 + 1
            d = date(year, month, 1)
            out.append(AreaTrendPoint(date=d, index=round(idx, 2)))
        return out

class HttpTrends(TrendsClient):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def price_index(self, area: GeoArea, months: int = 12) -> List[AreaTrendPoint]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self.base_url}/price-index",
                params={"area": area.name, "code": area.code, "months": months}
            )
            r.raise_for_status()
            items = r.json()
            return [AreaTrendPoint(date=date.fromisoformat(i["date"]), index=float(i["index"])) for i in items]

def trends_client():
    if settings.TRENDS_PROVIDER == "http" and settings.TRENDS_BASE_URL:
        return HttpTrends(settings.TRENDS_BASE_URL)
    return MockTrends()
