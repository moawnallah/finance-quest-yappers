"""Hard engine: block programs run on the simulation core (docs/hard_engine.md).

Backend usage:
    from hard import load_records, question_view, reveal_view, score
    tasks = load_records()                     # {id: record} from output/hard_tasks.json
    question_view(tasks[tid])                  # GET /tasks/{id}
    score(tasks[tid], program)                 # POST /answers: accepted, points 51-100, tests, story, futures
    reveal_view(tasks[tid])                    # with the result
"""
import json
from pathlib import Path

from common import AttemptError

from .task import PUBLIC_OPTIONAL, public_tests, question_view, reveal_view, run_public, score, secrets

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "hard_tasks.json"


def load_records(path: Path | str = OUTPUT) -> dict[str, dict]:
    return {t["id"]: t for t in json.loads(Path(path).read_text(encoding="utf-8"))["tasks"]}


__all__ = ["AttemptError", "PUBLIC_OPTIONAL", "load_records", "public_tests", "question_view", "reveal_view", "run_public", "score", "secrets"]
