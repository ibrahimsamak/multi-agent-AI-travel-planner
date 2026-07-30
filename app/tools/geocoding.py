from __future__ import annotations
import asyncio
from functools import lru_cache
import httpx
from app.config import get_settings

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def geocode(place: str)-> dict | None:
    cached = _cache_get(place.lower().strip())
    print(f"Cache hit for {place}: {cached}")
    if cached is not None:
        return cached

    settings = get_settings()
    params = {"q": place, "format": "json", "limit": 1}
    headers = {"User-Agent": f"ai-travel-planner/0.1 ({settings.contact_email})"}
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        print(f"Geocoding {place} via Nominatim...")
        resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        top = data[0]
        result = {"lat": top["lat"], "lon": top["lon"], "display_name": top["display_name"]}
        _cache_set(place.lower().strip(), result)
        return result

@lru_cache(maxsize=512)
def _cache_box(key: str) -> dict:
    return {}

def _cache_get(key: str) -> dict | None:
    return _cache_box(key).get("value")

def _cache_set(key: str, value: dict) -> None:
    _cache_box(key)["value"] = value


if __name__ == "__main__":
    print(asyncio.run(geocode("New York, United States")))
