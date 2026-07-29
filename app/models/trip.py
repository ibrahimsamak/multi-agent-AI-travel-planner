from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class TimeOfDay(str, Enum):
    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"


class ItemCategory(str, Enum):
    flight = "flight"
    lodging = "lodging"
    food = "food"
    activity = "activity"
    trasnport = "transport"


class TripRequest(BaseModel):
    destination: str = Field(...,description="City or region the user wants to visit")
    duration_days: int = Field(..., gt=0, le=90)
    budget_total: float = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    origin: str | None = Field(default=None, description="Origin city; needed for flight pricing")
    travelers: int = Field(default=1, gt=0)

    @field_validator("destination", "origin")
    @classmethod
    def _clean_place(cls, v:str | None) -> str:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Place cannot be empty")
        return v

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v:str ) -> str:
        return v.upper()


class ItineraryItem(BaseModel):
    day: int = Field(..., ge=1)
    time_of_day: TimeOfDay
    category: ItemCategory
    title: str
    description: str = ""
    cost: float = Field(default=0.0, ge=0)
    currency: str = "USD"
    source_url: str | None = None


class TripPlan(BaseModel):
    request: TripRequest
    items: list[ItineraryItem] = Field(default_factory=list)
    total_cost: float = 0.0
    within_budget: bool = True
    remaining_budget: float = 0.0
    summary: str = ""

    def recompute_budget(self) -> "TripPlan":
        self.total_cost = round(sum(item.cost for item in self.items), 2)
        self.remaining_budget = round(self.request.budget_total - self.total_cost, 2)
        self.within_budget = self.total_cost <= self.request.budget_total
        return self


if __name__ == "__main__":
    req = TripRequest(destination="  Tokyo ", duration_days=5, budget_total=2000, currency="usd")
    plan = TripPlan(request=req)
    plan.items.append(
        ItineraryItem(day=1, time_of_day="morning", category="lodging", title="Hotel night", cost=120, currency="USD")
    )
    plan.recompute_budget()
    print(plan.model_dump_json(indent=2))
