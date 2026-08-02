from __future__ import annotations
from agents import Agent, function_tool
from app.config import get_settings
from app.tools.currency import convert

@function_tool
async def convert_currency(amount:float, base:str, target:str)->float:
    """Convert an amount between ISO currencies (fails soft to the input amount)."""
    return await convert(amount=amount, base=base, target=target)

def build_budget_agent() -> Agent:
    return Agent(
        name="BudgetAgent",
        instructions=(
            "You are the budget enforcer. Given the chosen flights, lodging, and "
            "activities with their prices, convert everything to the user's currency "
            "with convert_currency, sum the total, and compare it to the budget. "
            "State the total, whether it's within budget, and the remaining amount. "
            "If it's over, suggest the smallest trade-offs (cheaper hotel, one fewer "
            "paid activity) to bring it back under."
        ),
        tools=[convert_currency],
        model=get_settings().agent_model,
    )
