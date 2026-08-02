from __future__ import annotations
import asyncio
from datetime import date, timedelta
from agents import Agent, Runner, set_default_openai_key, trace
from agents.exceptions import MaxTurnsExceeded
from pydantic import BaseModel, Field
from app.config import get_settings

from app.agents.budget import build_budget_agent
from app.agents.flights import build_flights_agent
from app.agents.food_activities import build_food_activities_agent
from app.agents.lodging import build_lodging_agent
from app.tools.apify_travel import flights_and_hotels_servers


from app.models.trip import ItineraryItem, TripPlan, TripRequest

class PlanDraft(BaseModel):
    items: list[ItineraryItem] = Field(default_factory=list)
    summary: str = ""


SCRAPER_MAX_TURNS = 5
FOOD_MAX_TURNS = 5


async def _run_research(agent: Agent, prompt: str, label: str, max_turns: int) -> str:
    try:
        res = await Runner.run(agent, prompt, max_turns=max_turns)
        return str(res.final_output)
    except MaxTurnsExceeded:
        return f"{label} data is unavailable (research did not converge in time)."


def compute_dates(request: TripRequest, lead_days:int=30)->tuple[str,str]:
    start = date.today()+timedelta(days=lead_days)
    end = start + timedelta(days=request.duration_days)
    return start.isoformat(), end.isoformat()


def build_assembler_agent() -> Agent:
    return Agent(
        name="PlanAssembler",
        instructions=(
            "You assemble a day-by-day travel itinerary from research notes. "
            "Produce concrete itinerary items (day, time_of_day, category, title, "
            "description, cost, currency), using the flight/hotel/activity prices "
            "from the notes. Spread activities across the trip's days. Respect the "
            "budget: if the budget analysis flags an overage, drop or swap the most "
            "expensive optional items. End with a short, friendly summary."
        ),
        output_type=PlanDraft,
        model=get_settings().agent_model,
    )


def _flights_prompt(req: TripRequest, departure: str) -> str:
    if not req.origin:
        return "No origin city was provided, so flights can't be priced. Return an empty list."
    return (f"Find flights from {req.origin} to {req.destination} departing {departure} "
            f"for {req.travelers} traveler(s). Prices in {req.currency}.")


def _lodging_prompt(req: TripRequest, check_in: str, check_out: str) -> str:
    return (f"Find hotels in {req.destination} from {check_in} to {check_out} "
            f"for {req.travelers} guest(s). Prices in {req.currency}.")


def _food_prompt(req: TripRequest) -> str:
    return (f"Suggest restaurants and attractions in {req.destination} for a "
            f"{req.duration_days}-day trip, and note any weather worth planning around. "
            f"Prices in {req.currency}.")


def _budget_prompt(req: TripRequest, research: dict[str, str]) -> str:
    return (
        f"Budget: {req.budget_total} {req.currency} total, {req.travelers} traveler(s), "
        f"{req.duration_days} days in {req.destination}.\n\n"
        f"FLIGHTS:\n{research['flights']}\n\n"
        f"LODGING:\n{research['lodging']}\n\n"
        f"FOOD & ACTIVITIES:\n{research['food']}\n\n"
        "Total the realistic costs, convert to the budget currency, and say whether it "
        "fits. If it's over, suggest the smallest trade-offs to bring it back under."
    )

def _assembler_prompt(req: TripRequest, research: dict[str, str], budget_notes: str, start_date: str, edit_notes: str | None) -> str:
    prompt = (
        f"Trip: {req.duration_days} days in {req.destination}, starting {start_date}, "
        f"{req.travelers} traveler(s), budget {req.budget_total} {req.currency}.\n\n"
        f"FLIGHTS:\n{research['flights']}\n\n"
        f"LODGING:\n{research['lodging']}\n\n"
        f"FOOD & ACTIVITIES:\n{research['food']}\n\n"
        f"BUDGET ANALYSIS:\n{budget_notes}\n\n"
        "Assemble the day-by-day itinerary now."
    )
    if edit_notes:
        prompt += f"\n\nAPPLY THESE USER EDITS TO THE PLAN:\n{edit_notes}"
    return prompt


async def research_and_draft(request: TripRequest, edit_notes:str | None=None)-> TripPlan:
    set_default_openai_key(get_settings().openai_api_key)
    with trace("travel-plan", metadata={"destination": request.destination,
                                        "mode": "edit" if edit_notes else "draft"}):
        start_date, end_date = compute_dates(request)
        async with flights_and_hotels_servers() as (flights_srv, hotels_srv):
            flights_agent = build_flights_agent([flights_srv] if flights_srv else [])
            lodging_agent = build_lodging_agent([hotels_srv] if hotels_srv else [])
            food_agent = build_food_activities_agent()

            flights_txt, lodging_txt, food_txt = await asyncio.gather(
                _run_research(flights_agent, _flights_prompt(request, start_date), "Flights", SCRAPER_MAX_TURNS),
                _run_research(lodging_agent, _lodging_prompt(request, start_date, end_date), "Lodging", SCRAPER_MAX_TURNS),
                _run_research(food_agent, _food_prompt(request), "Food & activities", FOOD_MAX_TURNS),
            )
        research = {"flights": flights_txt, "lodging": lodging_txt, "food": food_txt}

        budget_res = await Runner.run(build_budget_agent(), _budget_prompt(request, research))
        draft_res = await Runner.run(build_assembler_agent(), _assembler_prompt(request, research, str(budget_res.final_output), start_date, edit_notes))
        draft: PlanDraft = draft_res.final_output
        plan = TripPlan(request=request, items=draft.items, summary=draft.summary)
        return plan.recompute_budget()


if __name__ == "__main__":
    import os
    if os.environ.get("DEBUG_AGENTS"):
        from agents import enable_verbose_stdout_logging
        enable_verbose_stdout_logging()

    async def _demo():
        req = TripRequest(destination="Lisbon", duration_days=2, budget_total=1000, currency="EUR", origin="Toronto")
        plan = await research_and_draft(req)
        print(plan.model_dump_json(indent=2))

    asyncio.run(_demo())
