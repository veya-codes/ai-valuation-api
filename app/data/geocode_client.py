import math
from datetime import date
from .base import GeocodeClient, GeocodeResult, GeoPoint, GeoArea
from ..core.config import settings
from ..core.utils import fnv1a_32, seeded_rand
import httpx

class MockGeocode(GeocodeClient):
    """
    Mock geocoder that turns the address string into a stable lat/lon and area.
    This is entirely deterministic and free of external dependencies.
    """
    async def resolve(self, address: str) -> GeocodeResult:
        seed = fnv1a_32(address)
        # Map seed to a lat/lon roughly within Canada bounds for realism
        lat = 42.0 + seeded_rand(seed, 1)[0] * (83.0 - 42.0) / 2  # 42..62 approx
        lon = -141.0 + seeded_rand(seed+1, 1)[0] * ( -52.0 + 141.0 )  # -141..-52
        point = GeoPoint(lat=round(lat, 6), lon=round(lon, 6))
        # Fake "area" from hash buckets
        area_names = ["Downtown", "West End", "Kitsilano", "Mount Pleasant", "Fairview", "Yaletown", "Oakridge"]
        idx = int(seeded_rand(seed+2, 1)[0] * len(area_names)) % len(area_names)
        area = GeoArea(name=area_names[idx], code=f"MLS-{idx:02d}")
        # Pretend city/province (choose a few for variety)
        cities = [("Vancouver","BC"),("Victoria","BC"),("Burnaby","BC"),("Surrey","BC"),("Kelowna","BC")]
        cidx = int(seeded_rand(seed+3,1)[0] * len(cities)) % len(cities)
        city, prov = cities[cidx]
        return GeocodeResult(point=point, area=area, city=city, province=prov)

    async def area_from_point(self, point: GeoPoint) -> GeoArea:
        # Use a quick hash of rounded coordinates to pick an area name
        s = f"{round(point.lat,2)},{round(point.lon,2)}"
        seed = fnv1a_32(s)
        area_names = ["Central", "North", "South", "East", "West"]
        idx = int(seeded_rand(seed, 1)[0] * len(area_names)) % len(area_names)
        return GeoArea(name=area_names[idx], code=f"MLS-{idx:02d}")

class HttpGeocode(GeocodeClient):
    """
    Placeholder for a real geocoding provider you control.
    Expects a simple JSON API at GEO_BASE_URL that returns point+area.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def resolve(self, address: str) -> GeocodeResult:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/resolve", params={"address": address})
            r.raise_for_status()
            j = r.json()
            return GeocodeResult(
                point=GeoPoint(lat=j["point"]["lat"], lon=j["point"]["lon"]),
                area=GeoArea(name=j["area"]["name"], code=j["area"].get("code")),
                city=j["city"], province=j["province"], country=j.get("country","Canada")
            )

    async def area_from_point(self, point: GeoPoint) -> GeoArea:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/area", params={"lat": point.lat, "lon": point.lon})
            r.raise_for_status()
            j = r.json()
            return GeoArea(name=j["name"], code=j.get("code"))

def geocode_client() -> GeocodeClient:
    """
    Factory picks mock or http based on env flags.
    """
    if settings.GEO_PROVIDER == "http" and settings.GEO_BASE_URL:
        return HttpGeocode(settings.GEO_BASE_URL)
    return MockGeocode()
