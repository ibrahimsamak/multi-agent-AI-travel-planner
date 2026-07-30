from __future__ import annotations
import asyncio
import httpx
from app.config import get_settings
from app.tools.geocoding import geocode

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def forecast_by_coords(lat: float, lon: float, days: int = 7) -> dict:
    days = max(1, min(days, 16))
    settings = get_settings()
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "forecast_days": days,
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        resp = await client.get(OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        return resp.json()


async def forecast_for_place(place: str, days: int = 7) -> dict | None:
    loc = await geocode(place)
    if loc is None:
        return None
    data = await forecast_by_coords(loc["lat"], loc["lon"], days)
    data["place"] = loc["display_name"]
    return data


if __name__ == "__main__":
    print(asyncio.run(forecast_for_place("Tokyo", days=3)))
