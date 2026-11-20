"""Data shapes and the two interfaces the tutor depends on (docs/tutor_agent.md, section 5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

MODES = ("explain_concept", "hint", "explain_result", "rephrase", "recommend_reading")
FREE_HINTS = 2  # hints 1-2 are free; every further hint lowers the task score (docs/tutor_agent.md)


@dataclass
class TutorRequest:
    mode: str
    user_id: str
    node: str
    message: str = ""
    task_id: str | None = None
    attempt_id: str | None = None   # set after submission; required for explain_result
    draft_response: dict | None = None
    hint_level: int = 1             # 1 concept, 2 example with other numbers, 3 pointer
    last_answer: str | None = None  # the text to rephrase


@dataclass
class TutorResponse:
    text: str
    links: list[dict]
    check_question: str
    hint_level: int | None
    hint_paid: bool
    fallback: bool
    intent: str
    checks_failed: list[str] = field(default_factory=list)
    event: dict = field(default_factory=dict)  # one llm_events row for the backend to store


@dataclass
class Completion:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


class LLMClient(Protocol):
    def complete(self, role: str, messages: list[dict], json_schema: dict | None,
                 max_tokens: int, contains_user_data: bool) -> Completion: ...


class ContextProvider(Protocol):
    """Implemented by the backend (database reads). Nothing here may return answers to the model
    except `reveal`, which returns None until the attempt is submitted."""

    def task_public(self, task_id: str) -> dict: ...
    def reveal(self, attempt_id: str) -> dict | None: ...
    def task_secrets(self, task_id: str) -> dict: ...  # {"strings": [...], "numbers": [...]}; for checks only
    def profile_aggregates(self, user_id: str) -> dict: ...
    def search_kb(self, node: str, query: str, k: int) -> list[dict]: ...
    def stored_explanation(self, key: str, mode: str) -> str: ...
