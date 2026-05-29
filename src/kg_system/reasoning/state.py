from __future__ import annotations

from typing import TypedDict


class ReasonerState(TypedDict, total=False):
    question: str
    subgraph: str
    reasoning_trace: list[str]
    answer: str
    next_action: str  # retrieve | reason | generate | end
    step_count: int
