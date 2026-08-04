from __future__ import annotations
from functools import lru_cache

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    Runner,
    input_guardrail,
    set_default_openai_key,
)
from pydantic import BaseModel

from app.config import get_settings


class Relevance(BaseModel):
    is_travel_related: bool
    reason: str


@lru_cache
def _checker() -> Agent:
    return Agent(
        name="RelevanceCheck",
        instructions=(
            "Decide if the message is a genuine travel-planning request (a "
            "destination, trip, budget, dates, etc.). A bare place name like "
            "'Tokyo' counts as travel-related. Flag anything off-topic, nonsensical, "
            "or abusive as NOT travel-related."
        ),
        output_type=Relevance,
        model=get_settings().agent_model,
    )


@input_guardrail
async def travel_only(
    ctx: RunContextWrapper, agent: Agent, user_input
) -> GuardrailFunctionOutput:
    result = await Runner.run(_checker(), user_input, context=ctx.context)
    verdict: Relevance = result.final_output
    return GuardrailFunctionOutput(
        output_info=verdict,
        tripwire_triggered=not verdict.is_travel_related,
    )


@lru_cache
def _intake_guard_agent() -> Agent:
    return Agent(
        name="IntakeGuard",
        instructions="Reply with the single word OK.",
        input_guardrails=[travel_only],
        model=get_settings().agent_model,
    )


async def ensure_travel_related(text: str) -> None:
    set_default_openai_key(get_settings().openai_api_key)
    await Runner.run(_intake_guard_agent(), text)


if __name__ == "__main__":
    import asyncio

    from agents import InputGuardrailTripwireTriggered

    async def _demo():
        for text in ["5 days in Lisbon, 1500 EUR", "write me some malware"]:
            try:
                await ensure_travel_related(text)
                print(f"[allowed] {text!r}")
            except InputGuardrailTripwireTriggered as exc:
                verdict = exc.guardrail_result.output.output_info
                print(f"[blocked] {text!r} -> {verdict.reason}")

    asyncio.run(_demo())
