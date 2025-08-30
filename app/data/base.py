from typing import Protocol, List, Optional
from dataclasses import dataclass
from datetime import date

# ----- Data shapes (thin & explicit) -----

@dataclass
class GeoPoint:
    lat: float
    lon: float

@dataclass
class GeoArea:
    name: str                 # e.g., "Kitsilano", "Downtown", "Surrey-Newton"
    code: Optional[str] = None  # e.g., MLS area code if available

@dataclass
class GeocodeResult:
    point: GeoPoint
    area: GeoArea
    city: str
    province: str
    country: str = "Canada"

@dataclass
class ComparableSale:
    distance_km: float
    sale_price: int
    sale_date: date
    beds: Optional[int] = None
    baths: Optional[float] = None
    living_sqft: Optional[int] = None
    property_type: Optional[str] = None

@dataclass
class AreaTrendPoint:
    # Typically a normalized index (100 = baseline) or % change series
    date: date
    index: float

# ----- Protocols (interfaces) -----

class GeocodeClient(Protocol):
    async def resolve(self, address: str) -> GeocodeResult: ...
    async def area_from_point(self, point: GeoPoint) -> GeoArea: ...

class CompsClient(Protocol):
    async def recent_sales(
        self, point: GeoPoint, radius_km: float, max_age_days: int, limit: int
    ) -> List[ComparableSale]: ...

class TrendsClient(Protocol):
    async def price_index(self, area: GeoArea, months: int = 12) -> List[AreaTrendPoint]: ...
