import pytest
import asyncio

from app.models.trip import TripRequest, TripPlan, ItineraryItem
from app.gradio_app import _parse_int, _parse_float

from app.hitl import approval_gate

def _plan(*costs):
    req = TripRequest(destination="Lisbon", duration_days=3, budget_total=1000, currency="EUR")
    items = [
                ItineraryItem(day=1, time_of_day="morning", category="activity", title=f"item{i}", cost=c, currency="EUR")
                for i, c in enumerate(costs)
            ]
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
    
@pytest.fixture
def trip_request():
    return TripRequest(destination="Lisbon", duration_days=3, budget_total=1000, currency="EUR")

@pytest.fixture
def make_plan(trip_request):
    def _make(*costs):
        items = [
            ItineraryItem(day=1, time_of_day="morning", category="activity", title=f"item{i}", cost=c, currency="EUR")
            for i, c in enumerate(costs)
        ]
        return TripPlan(request=trip_request, items=items)
    return _make

def test_recompute_within_budget(make_plan):
    plan = make_plan(300, 200).recompute_budget()
    assert plan.total == 500
    assert plan.within_budget is True
    
@pytest.fixture
def fake_settings(mocker, tmp_path):
    settings = mocker.patch("app.hitl.approval_gate.get_settings").return_value
    settings.session_store_dir = str(tmp_path)  
    return settings


def test_open_gate_finalizes_when_no_approval_needed(mocker, fake_settings, make_plan):
    mocker.patch("app.hitl.approval_gate._use_configured_key")
    mocker.patch("app.hitl.approval_gate.build_finalizer_agent")
    run = mocker.patch("app.hitl.approval_gate.Runner.run", new_callable=mocker.AsyncMock)
    run.return_value.interruptions = []
    run.return_value.final_output = "Plan finalized"

    result = asyncio.run(approval_gate.open_gate("s1", make_plan(100)))

    assert result["status"] == "finalized"
    assert result["message"] == "Plan finalized"
    run.assert_awaited_once()                      
    assert not approval_gate.has_pending("s1")    


def test_session_path_uses_configured_folder(fake_settings, tmp_path):
    assert approval_gate._session_path("abc") == tmp_path / "abc.json"

