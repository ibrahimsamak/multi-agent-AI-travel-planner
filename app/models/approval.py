from __future__ import annotations
from typing import Literal
from pydantic import BaseModel

class ApprovalDecision(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    edits: str | None = None
    session_id: str
