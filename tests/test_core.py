import pytest

from app.models.trip import TripRequest, TripPlan, ItineraryItem
from app.gradio_app import _parse_int, _parse_float


def _plan(*costs):
    req = TripRequest(destination="Lisbon", duration_days=3, budget_total=1000, currency="EUR")
    items = [ItineraryItem(day=1, time_of_day="morning", category="activity",
                           title=f"item{i}", cost=c, currency="EUR")
             for i, c in enumerate(costs)]
    return TripPlan(request=req, items=items)


def test_recompute_within_budget():
    plan = _plan(300, 200).recompute_budget()
    assert plan.total_cost == 500
    assert plan.remaining_budget == 500
    assert plan.within_budget is True


def test_recompute_over_budget():
    plan = _plan(800, 400).recompute_budget()
    assert plan.total_cost == 1200
    assert plan.within_budget is False


@pytest.mark.parametrize("text,expected", [("5", 5), ("about 7 days", 7), ("10-day trip", 10)])
def test_parse_int(text, expected):
    assert _parse_int(text) == expected


@pytest.mark.parametrize("text,expected", [("2000", 2000.0), ("2,000 USD", 2000.0), ("$1500.50", 1500.50)])
def test_parse_float(text, expected):
    assert _parse_float(text) == expected
