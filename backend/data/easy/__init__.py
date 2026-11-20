"""Easy engine (docs/task_engines.md, "Easy engine"): cards and quiz items per node, plus the prerequisite test.

Backend usage:
    from easy import load_nodes, node_view, question_view, reveal_view, score, secrets, prerequisite_test
    nodes = load_nodes()                               # {node_id: record} from output/easy.json
    items = {i["id"]: i for n in nodes.values() for i in n["items"]}
    node_view(nodes["I4"])                             # GET /nodes/{id}: cards + items without answers
    score(items["i4.e1"], 1, confidence=4)             # POST /answers
    reveal_view(items["i4.e1"])                        # returned with the score
    prerequisite_test(nodes, "D1", seed=user_id)       # item ids for the node's prerequisite test
    test_out(nodes, "I4", seed=user_id)                # 2 own check items when the router marks I4 "probably known"
"""
import json
from pathlib import Path

from common import AttemptError

from .node import (easy_done, node_done, node_view, prerequisite_passed, prerequisite_test, question_view,
                   reveal_view, score, secrets, test_out)

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "easy.json"


def load_nodes(path: Path | str = OUTPUT) -> dict[str, dict]:
    return {n["node"]: n for n in json.loads(Path(path).read_text(encoding="utf-8"))["nodes"]}


__all__ = ["AttemptError", "load_nodes", "node_view", "question_view", "reveal_view", "score", "secrets",
           "prerequisite_test", "prerequisite_passed", "test_out", "easy_done", "node_done"]
