"""Bridge to the task engines in backend/data (docs/task_engines.md): the easy engine (cards and items)
and the medium engine (day-X chart tasks). The engines own validation, views and scoring; this module
loads their compiled output, decides what is served, and works out node completion from stored attempts."""
import sys
from dataclasses import dataclass, field
from functools import lru_cache

from app.config import BACKEND_DIR, ENGINE_OUTPUT_DIR, SERVE_DRAFTS

DATA_DIR = BACKEND_DIR / "data"
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))

import easy  # noqa: E402
import hard  # noqa: E402
import medium  # noqa: E402
from common import AttemptError, localize  # noqa: E402

__all__ = ["AttemptError", "Catalog", "catalog", "localize", "node_status", "easy", "hard", "medium"]


@dataclass
class Catalog:
    """What the API serves: compiled nodes, their easy items, and medium tasks."""
    nodes: dict[str, dict]
    tasks: dict[str, dict]
    hard_tasks: dict[str, dict] = field(default_factory=dict)
    items: dict[str, dict] = field(init=False)
    tasks_by_node: dict[str, list[dict]] = field(init=False)

    def __post_init__(self):
        self.items = {i["id"]: i for n in self.nodes.values() for i in n["items"]}
        self.tasks_by_node = {}
        for t in self.tasks.values():
            self.tasks_by_node.setdefault(t["node"], []).append(t)
        self.hard_by_node: dict[str, list[dict]] = {}
        for t in self.hard_tasks.values():
            self.hard_by_node.setdefault(t["node"], []).append(t)

    @classmethod
    def load(cls, serve_drafts: bool = SERVE_DRAFTS) -> "Catalog":
        nodes = easy.load_nodes(ENGINE_OUTPUT_DIR / "easy.json")
        tasks = medium.load_records(ENGINE_OUTPUT_DIR / "medium_tasks.json")
        hard_path = ENGINE_OUTPUT_DIR / "hard_tasks.json"
        hard_tasks = hard.load_records(hard_path) if hard_path.exists() else {}
        nodes = {k: v for k, v in nodes.items() if serve_drafts or v["live"]}
        # A task is served only with its node, so completion always has a node to count toward.
        keep = lambda recs: {k: v for k, v in recs.items() if (serve_drafts or v["live"]) and v["node"] in nodes}
        return cls(nodes=nodes, tasks=keep(tasks), hard_tasks=keep(hard_tasks))

    def find(self, task_id: str) -> tuple[str, dict] | None:
        """('easy', item), ('medium', task) or ('hard', task), or None."""
        if task_id in self.items:
            return "easy", self.items[task_id]
        if task_id in self.tasks:
            return "medium", self.tasks[task_id]
        if task_id in self.hard_tasks:
            return "hard", self.hard_tasks[task_id]
        return None


@lru_cache(maxsize=1)
def catalog() -> Catalog:
    return Catalog.load()


def _latest(attempts, context: str) -> dict[str, float | None]:
    """Latest score per task id for one context. `attempts` must be in submission order."""
    out: dict[str, float | None] = {}
    for a in attempts:
        if a.context == context:
            out[a.task_id] = a.score
    return out


def _drawn_scores(ids: list[str], latest: dict[str, float | None]) -> list[float]:
    """Scores for a drawn test (prerequisite or test-out); empty until every drawn item is answered."""
    if not ids or any(latest.get(i) is None for i in ids):
        return []
    return [latest[i] for i in ids]


def node_status(cat: Catalog, node_id: str, user_id: str, attempts) -> dict:
    """Completion of one node for one user (docs/task_engines.md, "Node completion").

    attempts: the user's Attempt rows with this node_id, in submission order.
    Choices the spec leaves open:
    - unanswered scored items count as 0 in the 0.8 average;
    - a passed test-out (the challenge) completes the whole node (decided 2026-11-21);
    - hard tasks are optional for completion;
    - a node with no medium task is done when its easy part is done.
    """
    node = cat.nodes[node_id]
    practice = _latest(attempts, "practice")
    scored = [i for i in node["items"] if i["scored"]]
    item_scores = [practice.get(i["id"]) or 0.0 for i in scored]
    answered = sum(1 for i in scored if practice.get(i["id"]) is not None)

    pre_ids = easy.prerequisite_test(cat.nodes, node_id, seed=user_id)
    pre_scores = _drawn_scores(pre_ids, _latest(attempts, "prerequisite"))
    out_ids = easy.test_out(cat.nodes, node_id, seed=user_id)
    out_scores = _drawn_scores(out_ids, _latest(attempts, "test_out"))

    easy_part = easy.easy_done(pre_scores, item_scores) or easy.prerequisite_passed(out_scores)

    tasks = cat.tasks_by_node.get(node_id, [])
    task_ids = {t["id"] for t in tasks}
    medium_scores = [a.score for a in attempts if a.task_id in task_ids and a.score is not None]
    if easy.prerequisite_passed(out_scores):
        done = True
    else:
        done = easy.node_done(easy_part, medium_scores) if tasks else easy_part

    return {
        "node": node_id,
        "easy_done": easy_part,
        "medium_passed": easy.node_done(True, medium_scores),
        "done": done,
        "items_answered": answered,
        "items_correct": sum(1 for x in item_scores if x >= 1.0),
        "items_total": len(scored),
        "item_average": round(sum(item_scores) / len(item_scores), 4) if item_scores else None,
        "prerequisite": {"items": pre_ids, "passed": easy.prerequisite_passed(pre_scores)},
        "test_out": {"items": out_ids, "passed": easy.prerequisite_passed(out_scores)},
        "medium": {"tasks": sorted(task_ids), "best_score": max(medium_scores) if medium_scores else None},
    }
