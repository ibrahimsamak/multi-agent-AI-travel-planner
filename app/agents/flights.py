from __future__ import annotations
from agents import Agent, function_tool
from app.config import get_settings


def build_flights_agent(mscp_server: list | None = None) -> Agent:
    return Agent(
        name="FlightsAgent",
        instructions=(
            "You find flight options within budget using the Google Flights scraper "
            "tool available to you. It expects IATA airport codes, so convert the "
            "origin and destination cities to their main airport codes (e.g. Toronto "
            "-> YYZ, Lisbon -> LIS) and pass those plus the departure date "
            "(YYYY-MM-DD). Call the scraper AT MOST ONCE: take the results it "
            "returns and summarize the best 2-3 itineraries with price, airline, "
            "stops, and duration. Do NOT re-call the tool to refine, retry, or wait "
            "for more — if it returns nothing, an error, or an empty/pending "
            "response, stop and say flights can't be priced. Likewise if you have no "
            "flights tool or no origin was given, say flights can't be priced and "
            "return nothing."
        ),
        mcp_servers= mscp_server or [],
        model= get_settings().agent_model
    )
