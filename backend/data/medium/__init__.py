"""Medium engine ("estimate and explain"), docs/task_engines.md. Implemented so far: chart + direction (day X).

Backend usage:
    from medium import load_records, question_view, reveal_view, score
    tasks = load_records()                               # {id: record} from output/medium_tasks.json
    question_view(tasks[tid])                            # GET /tasks/{id}
    score(tasks[tid], "down", ["guidance", "priced_in"], confidence=4)   # POST /answers
    reveal_view(tasks[tid])                              # returned with the score
"""
import json
from pathlib import Path

from .task import AttemptError, question_view, reveal_view, score

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "medium_tasks.json"


def load_records(path: Path | str = OUTPUT) -> dict[str, dict]:
    return {t["id"]: t for t in json.loads(Path(path).read_text(encoding="utf-8"))["tasks"]}


__all__ = ["AttemptError", "load_records", "question_view", "reveal_view", "score"]
