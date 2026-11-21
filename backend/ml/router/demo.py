"""Demo mode on top of the router (docs/onboarding_router.md, "Demo mode").

The router recommends a path for everyone. In the demo only some nodes have content, so:
- if the recommended path uses only built nodes, the user gets it; if it is part of a demo path
  (the investor's router path I4 > I5 is part of I4 > I5 > P1 > P4), the user gets that demo path;
- otherwise the user sees the recommendation, is told it is not ready yet, and picks one of the
  demo paths. The closest demo path comes first (overlap with the recommendation).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .router import tree

HERE = Path(__file__).resolve().parent

NOT_READY = ("We're sorry: your recommended path would be {path}, but it is not ready yet. "
             "Please choose one of the two paths we have prepared.")
FINISHED = ("Thank you for finishing the path. This is a demo, and we are very happy you tested it: we hope you "
            "learned something you can use. If you like, try the other path too.")


@lru_cache(maxsize=1)
def demo_paths() -> dict[str, dict]:
    return yaml.safe_load((HERE / "demo_paths.yaml").read_text(encoding="utf-8"))


def _challenges(nodes: list[str]) -> list[str]:
    """Prerequisites of the path that are not on it: offered as 2-question challenges."""
    t = tree()
    out = []
    for k in nodes:
        for a in t[k]["after"]:
            if a not in nodes and a not in out:
                out.append(a)
    return out


def _option(path_id: str, recommended: list[str]) -> dict:
    p = demo_paths()[path_id]
    rec, nodes = set(recommended), set(p["nodes"])
    overlap = round(len(rec & nodes) / len(rec | nodes), 3) if rec | nodes else 0.0
    return {"id": path_id, "title": p["title"], "for": p["for"], "nodes": p["nodes"], "hard": p.get("hard", {}),
            "challenges": _challenges(p["nodes"]), "overlap": overlap,
            "shared_nodes": [k for k in p["nodes"] if k in rec]}


def match(result: dict, available: set[str]) -> dict:
    """result: router.route() output. available: nodes that have content. Returns the demo block."""
    t = tree()
    recommended = [p["node"] for p in result["path"]]
    missing = [k for k in recommended if k not in available]
    options = sorted((_option(pid, recommended) for pid in demo_paths()),
                     key=lambda o: (-o["overlap"], -sum(result["priority"].get(k, 0) for k in o["nodes"])))
    if not missing:
        containing = [o for o in options if set(recommended) <= set(o["nodes"])]
        if containing:
            o = containing[0]
            return {"status": "ready", "path_id": o["id"], "path": o["nodes"], "hard": o["hard"], "challenges": o["challenges"],
                    "recommended": recommended, "options": options, "message": None}
        return {"status": "ready", "path_id": "personal", "path": recommended, "challenges": _challenges(recommended),
                "recommended": recommended, "options": options, "message": None}
    titles = " > ".join(t[k]["title"] for k in recommended)
    return {"status": "not_ready", "path_id": None, "path": None, "challenges": [], "recommended": recommended,
            "missing": missing, "options": options, "closest": options[0]["id"],
            "message": NOT_READY.format(path=titles)}


def finished(path_id: str) -> dict:
    """What to show when a demo path is finished: thanks, the demo note, and the other path."""
    others = [pid for pid in demo_paths() if pid != path_id]
    other = others[0] if others else None
    return {"message": FINISHED,
            "feedback": {"optional": True, "ask": "If you are willing, tell us how it went: one tap to rate, a comment if you like."},
            "other_path": None if other is None else {"id": other, **{k: demo_paths()[other][k] for k in ("title", "for", "nodes")}}}
