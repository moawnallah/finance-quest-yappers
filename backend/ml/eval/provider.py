"""A ContextProvider built from the repo content, for evaluation runs before the backend exists.

- passages: the cards in backend/content/nodes, drafts included (eval only; the real ingest
  rejects unreviewed cards);
- tasks: backend/data/output/medium_tasks.json (built by the medium engine);
- attempt ids: "<task_id>:submitted" means the attempt was submitted, so reveal() returns it;
- learners: two fixed personas from docs/archive/demo_plan.md.
"""
from __future__ import annotations

import json
from pathlib import Path

from tutor import kb

BACKEND = Path(__file__).resolve().parents[2]
TASKS = BACKEND / "data" / "output" / "medium_tasks.json"

PERSONAS = {
    "young_adult": {"age_band": "25-39", "goal": "first investment", "horizon": "10+ years",
                    "mastery": {"S1": 0.66, "I1": 0.70, "I2": 0.42, "I4": 0.42, "P1": 0.35}, "calibration_gap": 0.25},
    "investor": {"age_band": "25-39", "goal": "grow investments", "horizon": "10+ years",
                 "mastery": {"I4": 0.75, "I5": 0.75, "P1": 0.76, "P2": 0.75, "P4": 0.45}, "calibration_gap": 0.05},
}


class ContentProvider:
    def __init__(self, content: Path = kb.CONTENT, tasks: Path = TASKS):
        self.nodes = kb.load_nodes(content)
        self.passages = kb.passages_from_cards(self.nodes, kb.load_sources(content))
        self.prereq = {n: d.get("after") or [] for n, d in self.nodes.items()}
        self.tasks = {t["id"]: t for t in json.loads(tasks.read_text(encoding="utf-8"))["tasks"]} if tasks.exists() else {}

    def task_public(self, task_id: str) -> dict:
        q = self.tasks[task_id]["question"]
        return {"id": task_id, "brief": q["brief"], "response": q["response"],
                "reasons": [b["text"] for b in q["reasons"]["boxes"]]}

    def reveal(self, attempt_id: str) -> dict | None:
        task_id, _, state = attempt_id.partition(":")
        if state != "submitted":
            return None
        r = self.tasks[task_id]["reveal"]
        texts = {b["id"]: b["text"] for b in self.tasks[task_id]["question"]["reasons"]["boxes"]}
        return {"text": r["text"], "outcome": r["outcome"], "truth": r["truth"],
                "reasons": [{"text": texts[b["id"]], "weight": b["weight"], "explain": b["explain"]} for b in r["reasons"]]}

    def task_secrets(self, task_id: str) -> dict:
        t = self.tasks[task_id]
        texts = {b["id"]: b["text"] for b in t["question"]["reasons"]["boxes"]}
        strings = [texts[b["id"]] for b in t["reveal"]["reasons"] if b["weight"] > 0]
        outcome = t["reveal"]["outcome"] or {}
        numbers = [abs(outcome["change"])] if "change" in outcome else []
        return {"strings": strings, "numbers": numbers}

    def profile_aggregates(self, user_id: str) -> dict:
        return PERSONAS[user_id]

    def search_kb(self, node: str, query: str, k: int) -> list[dict]:
        return kb.search(self.passages, node, query, k, self.prereq)

    def stored_explanation(self, key: str, mode: str) -> str:
        # The reveal text is the answer: only after submission (explain_result). A hint that falls back
        # before submission gets the node's first card instead.
        if key in self.tasks and mode == "explain_result":
            text = self.tasks[key]["reveal"]["text"]
            return text["en"] if isinstance(text, dict) else text
        if key in self.tasks:
            key = self.tasks[key]["node"]
        cards = self.nodes.get(key, {}).get("cards") or []
        return cards[0]["body"] if cards else "Open the cards for this topic."
