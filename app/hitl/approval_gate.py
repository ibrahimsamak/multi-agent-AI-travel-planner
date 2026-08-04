from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from agents import Agent, RunContextWrapper, Runner, RunState, function_tool, set_default_openai_key
from app.config import get_settings
from app.models.trip import TripPlan


def _use_configured_key() -> None:
    set_default_openai_key(get_settings().openai_api_key)


@dataclass
class PlanContext:
    draft: TripPlan


@function_tool(needs_approval=True)
async def finalize_plan(ctx: RunContextWrapper[PlanContext], note: str = "confirmed") -> str:
    """Lock in the approved travel plan. Requires human approval before it runs."""
    plan = ctx.context.draft
    return (
        f"Plan finalized: {len(plan.items)} items, total "
        f"{plan.total_cost} {plan.request.currency} "
        f"(within budget: {plan.within_budget})."
    )


def build_finalizer_agent() -> Agent:
    return Agent(
        name="Finalizer",
        instructions=(
            "Call finalize_plan exactly once to lock in the plan, then stop. "
            "Do not call any other tool and do not add commentary."
        ),
        tools=[finalize_plan],
        model=get_settings().agent_model,
    )


def _store_dir() -> Path:
    path = Path(get_settings().session_store_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_path(session_id: str) -> Path:
    return _store_dir() / f"{session_id}.json"


def _save(session_id: str, state: RunState, draft: TripPlan) -> None:
    payload = {
        "state": state.to_json(context_serializer=lambda _ctx: {}),
        "draft": draft.model_dump(mode="json"),
    }
    _session_path(session_id).write_text(json.dumps(payload), encoding="utf-8")


async def _load(session_id: str) -> tuple[RunState, TripPlan] | None:
    path = _session_path(session_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    draft = TripPlan.model_validate(payload["draft"])
    agent = build_finalizer_agent()
    state = await RunState.from_json(
        agent,
        payload["state"],
        context_override=RunContextWrapper(context=PlanContext(draft=draft)),
    )
    return state, draft


async def open_gate(session_id: str, draft: TripPlan) -> dict:
    _use_configured_key()
    agent = build_finalizer_agent()
    ctx = PlanContext(draft=draft)
    result = await Runner.run(agent, "Finalize the plan.", context=ctx)

    if result.interruptions:
        _save(session_id, result.to_state(), draft)
        return {"status": "awaiting_approval", "draft": draft}

    return {"status": "finalized", "draft": draft, "message": str(result.final_output)}


async def resolve_gate(session_id: str, approve: bool) -> dict:
    _use_configured_key()
    loaded = await _load(session_id)
    if loaded is None:
        raise KeyError(f"no pending approval for session {session_id!r}")
    state, draft = loaded

    for item in state.get_interruptions():
        if approve:
            state.approve(item)
        else:
            state.reject(item)

    agent = build_finalizer_agent()
    result = await Runner.run(agent, state)
    _session_path(session_id).unlink(missing_ok=True)

    if approve:
        return {"status": "finalized", "draft": draft, "message": str(result.final_output)}
    return {"status": "rejected", "message": str(result.final_output)}


def has_pending(session_id: str) -> bool:
    return _session_path(session_id).exists()


if __name__ == "__main__":
    from app.agents.orchestrator import research_and_draft
    from app.models.trip import TripRequest

    async def _demo():
        req = TripRequest(destination="Lisbon", duration_days=3, budget_total=1200, currency="EUR", origin="Toronto")
        draft = await research_and_draft(req)
        gate = await open_gate("demo-session", draft)
        print("gate status:", gate["status"])
        print("persisted at:", _session_path("demo-session"))
        final = await resolve_gate("demo-session", approve=True)
        print("after approve:", final["message"])
    asyncio.run(_demo())
