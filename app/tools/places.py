from __future__ import annotations
import asyncio
import httpx
from app.config import get_settings
from app.tools.geocoding import geocode
GEOAPIFY_URL = "https://api.geoapify.com/v2/places"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

GEOAPIFY_CATEGORY = {
    "restaurant": "catering.restaurant",
    "cafe": "catering.cafe",
    "attraction": "tourism.sights",
    "activity": "entertainment",
}

OSM_FILTER = {
    "restaurant": '["amenity"="restaurant"]',
    "cafe": '["amenity"="cafe"]',
    "attraction": '["tourism"="attraction"]',
    "activity": '["leisure"="park"]',
}


async def geoapify_places(lat: float, lon: float, kind: str, radius_m: int, limit: int)-> list[dict]:
    settings = get_settings()
    if not settings.geoapify_key:
        return []
    pararms = {
        "categories": GEOAPIFY_CATEGORY.get(kind, "catering.restaurant"),
        "filter": f"circle:{lon},{lat},{radius_m}",
        "bias": f"proximity:{lon},{lat}",
        "limit": limit,
        "apiKey": settings.geoapify_api_key,
    }

    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        resp = await client.get(GEOAPIFY_URL, params=pararms)
        resp.raise_for_status()
        data = resp.json()
    out = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        if props.get("name"):
            out.append({
                "name": props.get("name"),
                "address": props.get("formatted"),
                "lat": props.get("lat"),
                "lon": props.get("lon"),
                "kind": kind,
            })
    return out


async def overpass_places(lat: float, lon: float, kind: str, radius_m: int, limit: int)-> list[dict]:
    settings = get_settings()
    tag = OSM_FILTER.get(kind, OSM_FILTER["restaurant"])
    query = (
        f"[out:json][timeout:25];"
        f"node{tag}(around:{radius_m},{lat},{lon});"
        f"out body {limit};"
    )
    async with httpx.Client(timeout=settings.request_timeout) as client:
        resp = await client.post(OVERPASS_URL, data=query)
        resp.raise_for_status()
        data = resp.json()
    out = []
    for el in data.get("elements", [])[:limit]:
        tags = el.get("tags", {})
        if tags.get("name"):
            out.append({
                "name": tags.get("name"),
                "category": kind,
                "address": tags.get("addr:street"),
                "lat": el.get("lat"),
                "lon": el.get("lon"),
                "source": "overpass",
            })
    return out


async def search_places(lat: float, lon: float, kind: str = "restaurant", radius_m: int = 2000, limit: int = 10) -> list[dict]:
    settings = get_settings()
    if settings.geoapify_api_key:
        try:
            res= await geoapify_places(lat,lon, kind, radius_m, limit)
            if res:
                return res
        except httpx.HTTPError:
            pass

    try:
        return await overpass_places(lat, lon, kind, radius_m, limit)
    except httpx.HTTPError:
        return []
