from __future__ import annotations
from agents import Agent, function_tool
from app.config import get_settings
from app.tools.geocoding import geocode
from app.tools.places import search_places
from app.tools.weather import forecast_for_place

@function_tool
async def find_places(place: str, kind:str="restaurant", limit:int = 5)-> list[dict]:
    """Find restaurants or attractions near a place.
    Args:
        place: destination city or neighborhood.
        kind: one of 'restaurant', 'cafe', 'attraction', 'activity'.
        limit: max results.
    """
    address = await geocode(place)
    if address is not None:
        return await search_places(lat=address.lat, lon=address.lon, kind=kind,limit=limit)
    else: 
        return {}

@function_tool
async def get_weather(place: str, days: int=7)-> dict:
    """Get a daily weather forecast (up to 16 days) for a place, for packing/timing tips."""
    data = await forecast_for_place(place,days=days)
    return data or {}


def build_food_activities_agent(mcp_servers: list | None = None) -> Agent:
    return Agent(
        name="FoodActivitiesAgent",
        instructions=(
            "You suggest restaurants and attractions for the destination and note "
            "any weather worth planning around. Use find_places for dining and "
            "sights, and get_weather for the forecast. Prefer a spread across the "
            "trip's days. If a Google Maps scraper tool is available, you may use it "
            "to enrich results when the free source is thin."
        ),
        tools=[find_places, get_weather],
        mcp_servers=mcp_servers or [],
        model=get_settings().agent_model,
    )
