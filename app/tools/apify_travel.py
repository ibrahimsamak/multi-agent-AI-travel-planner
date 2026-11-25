from __future__ import annotations
from contextlib import AsyncExitStack, asynccontextmanager
from app.config import get_settings
from agents.mcp import MCPServerStreamableHttp

APIFY_MCP_URL = "https://mcp.apify.com/"

FLIGHTS_ACTOR = "brilliant_gum/google-flights-scraper"
HOTELS_ACTOR = "voyager/booking-scraper"


def _server(tools: list[str], name: str):
    settings = get_settings()
    if not settings.apify_token:
        return None
    return MCPServerStreamableHttp(
        name=name,
        params={
            "url": f"{APIFY_MCP_URL}?tools={','.join(tools)}",
            "headers": {"Authorization": f"Bearer {settings.apify_token}"}
            },
        cache_tools_list=True,
        client_session_timeout_seconds=100
    )

def build_flight_server():
    return _server([FLIGHTS_ACTOR], "apify_flights")

def build_hotel_server():
    return _server([HOTELS_ACTOR], "apify_hotels")


@asynccontextmanager
async def flights_and_hotels_servers():
    flights = build_flight_server()
    hotels = build_hotel_server()
    # AsyncExitStack is a container that enters several context managers and remembers each one so it can exit them all later
    async with AsyncExitStack() as stack:
        for srv in (flights, hotels):
            if srv is not None:
                await stack.enter_async_context(srv)
        yield flights, hotels
