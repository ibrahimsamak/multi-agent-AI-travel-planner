from __future__ import annotations

import re
from uuid import uuid4

import gradio as gr
from agents import InputGuardrailTripwireTriggered
from pydantic import ValidationError

from app.agents.guardrails import ensure_travel_related
from app.agents.orchestrator import research_and_draft
from app.hitl.approval_gate import open_gate, resolve_gate
from app.models.trip import TripPlan, TripRequest

ASK_DEST, ASK_DUR, ASK_BUD, ASK_ORIG, AWAIT, DONE = (
    "ask_dest", "ask_dur", "ask_bud", "ask_orig", "await_approval", "done"
)

QUESTIONS = {
    ASK_DEST: "Where do you want to go?",
    ASK_DUR: "How long will you be there? (number of days)",
    ASK_BUD: "What's your total budget? (e.g. 2000 USD)",
    ASK_ORIG: "Which city are you flying from? (optional — type 'skip' to leave out flights)",
}


def new_state() -> dict:
    return {"stage": ASK_DEST, "req": {}, "session_id": None, "draft": None}


def _bot(history: list, text: str) -> list:
    return history + [{"role": "assistant", "content": text}]


def _btns(visible: bool):
    return gr.update(visible=visible), gr.update(visible=visible)


def _parse_int(s: str) -> int:
    m = re.search(r"\d+", s.replace(",", ""))
    if not m:
        raise ValueError("please give a number of days")
    return int(m.group())


def _parse_float(s: str) -> float:
    m = re.search(r"\d+(?:\.\d+)?", s.replace(",", ""))
    if not m:
        raise ValueError("please give a budget amount")
    return float(m.group())


def render_plan(plan: TripPlan) -> str:
    lines = [f"### {plan.request.destination} — {plan.request.duration_days} days"]
    by_day: dict[int, list] = {}
    for it in plan.items:
        by_day.setdefault(it.day, []).append(it)
    for day in sorted(by_day):
        lines.append(f"\n**Day {day}**")
        for it in by_day[day]:
            cost = f" — {it.cost:.0f} {it.currency}" if it.cost else ""
            tod = getattr(it.time_of_day, "value", it.time_of_day)
            lines.append(f"- _{tod}_ · {it.title}{cost}")
    status = "within budget ✅" if plan.within_budget else "over budget ⚠️"
    lines.append(
        f"\n**Total:** {plan.total_cost:.0f} {plan.request.currency} of "
        f"{plan.request.budget_total:.0f} — {status} "
        f"({plan.remaining_budget:.0f} left)"
    )
    if plan.summary:
        lines.append(f"\n{plan.summary}")
    return "\n".join(lines)


async def _make_draft(state: dict, edit_notes: str | None = None):
    req = TripRequest(**state["req"])
    plan = await research_and_draft(req, edit_notes=edit_notes)
    session_id = state["session_id"] or uuid4().hex
    await open_gate(session_id, plan)
    return plan, session_id


async def _approve(history, state):
    history = _bot(history, "Generating your full plan…")
    yield history, state, "", *_btns(False)
    result = await resolve_gate(state["session_id"], approve=True)
    plan = result.get("draft") or state["draft"]
    state["stage"] = DONE
    history = _bot(history, "✅ **Approved.** Your finalized plan:\n\n" + render_plan(plan))
    yield history, state, "", *_btns(False)


async def _reject(history, state):
    await resolve_gate(state["session_id"], approve=False)
    state.clear()
    state.update(new_state())
    history = _bot(history, "Plan discarded — let's start over.\n\n" + QUESTIONS[ASK_DEST])
    yield history, state, "", *_btns(False)


async def on_submit(message, history, state):
    message = (message or "").strip()
    if not message:
        yield history, state, "", *_btns(state["stage"] == AWAIT)
        return

    history = history + [{"role": "user", "content": message}]
    yield history, state, "", *_btns(False)

    stage = state["stage"]
    try:
        if stage == ASK_DEST:
            try:
                await ensure_travel_related(message)
            except InputGuardrailTripwireTriggered:
                yield _bot(history, "I can only help plan trips. " + QUESTIONS[ASK_DEST]), \
                    state, "", *_btns(False)
                return
            state["req"]["destination"] = message
            state["stage"] = ASK_DUR
            yield _bot(history, QUESTIONS[ASK_DUR]), state, "", *_btns(False)

        elif stage == ASK_DUR:
            state["req"]["duration_days"] = _parse_int(message)
            state["stage"] = ASK_BUD
            yield _bot(history, QUESTIONS[ASK_BUD]), state, "", *_btns(False)

        elif stage == ASK_BUD:
            state["req"]["budget_total"] = _parse_float(message)
            state["stage"] = ASK_ORIG
            yield _bot(history, QUESTIONS[ASK_ORIG]), state, "", *_btns(False)

        elif stage == ASK_ORIG:
            if message.lower() not in ("skip", "none", "no"):
                state["req"]["origin"] = message
            history = _bot(history, "Researching flights, hotels, and activities… one moment.")
            yield history, state, "", *_btns(False)
            plan, session_id = await _make_draft(state)
            state.update(draft=plan, session_id=session_id, stage=AWAIT)
            history = _bot(history, render_plan(plan) +
                           "\n\n**Approve** this plan, **Reject** it, or just type what you'd like changed.")
            yield history, state, "", *_btns(True)

        elif stage == AWAIT:
            low = message.lower()
            if low in ("yes", "y", "approve", "confirm", "ok", "okay"):
                async for out in _approve(history, state):
                    yield out
            elif low in ("no", "n", "reject", "cancel", "restart"):
                async for out in _reject(history, state):
                    yield out
            else:
                history = _bot(history, "Updating the plan with your changes…")
                yield history, state, "", *_btns(False)
                plan, session_id = await _make_draft(state, edit_notes=message)
                state.update(draft=plan, session_id=session_id)
                history = _bot(history, render_plan(plan) +
                               "\n\n**Approve**, **Reject**, or suggest more changes.")
                yield history, state, "", *_btns(True)

        else:
            yield _bot(history, "Your plan is ready above. Reload the page to plan another trip."), \
                state, "", *_btns(False)

    except (ValueError, ValidationError) as e:
        msg = QUESTIONS.get(state["stage"], "Let's try that again.")
        yield _bot(history, f"Hmm, I couldn't read that ({e}). {msg}"), state, "", *_btns(state["stage"] == AWAIT)


async def on_approve(history, state):
    if state["stage"] != AWAIT:
        yield history, state, "", *_btns(False)
        return
    async for out in _approve(history, state):
        yield out


async def on_reject(history, state):
    if state["stage"] != AWAIT:
        yield history, state, "", *_btns(False)
        return
    async for out in _reject(history, state):
        yield out


def on_load():
    return [{"role": "assistant", "content": QUESTIONS[ASK_DEST]}], new_state()


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="AI Travel Planner") as demo:
        gr.Markdown("## ✈️ AI Travel Planner\nAnswer three quick questions and I'll plan your trip.")
        chatbot = gr.Chatbot(height=520, label="Planner")
        state = gr.State(new_state())
        with gr.Row():
            txt = gr.Textbox(placeholder="Type your answer…", show_label=False,
                             scale=8, container=False)
            send = gr.Button("Send", scale=1, variant="primary")
        with gr.Row():
            approve_btn = gr.Button("✅ Approve", visible=False, variant="primary")
            reject_btn = gr.Button("❌ Reject", visible=False, variant="stop")

        outputs = [chatbot, state, txt, approve_btn, reject_btn]
        txt.submit(on_submit, [txt, chatbot, state], outputs)
        send.click(on_submit, [txt, chatbot, state], outputs)
        approve_btn.click(on_approve, [chatbot, state], outputs)
        reject_btn.click(on_reject, [chatbot, state], outputs)
        demo.load(on_load, None, [chatbot, state])
    return demo


demo = build_demo()

if __name__ == "__main__":
    demo.launch()
