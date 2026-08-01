from __future__ import annotations
from agents import Agent, function_tool
from app.config import get_settings

def build_lodging_agent(mcp_server: list | None=None)-> Agent:
    return Agent(
        name="LodgingAgent",
        instructions=(
            "You find hotels within the nightly budget using the Booking.com hotel "
            "scraper tool available to you. Call it AT MOST ONCE with the destination "
            "and the check-in / check-out dates, then summarize the best 2-3 stays "
            "with name, price, and rating. Do NOT re-call the tool to refine, retry, "
            "or wait for more — if it returns nothing, an error, or an empty/pending "
            "response, stop and say hotels can't be searched. Likewise if you have no "
            "hotel tool, say hotels can't be searched and return nothing."
        ),
        mcp_servers= mcp_server or [],
        model=get_settings().agent_model
    )
