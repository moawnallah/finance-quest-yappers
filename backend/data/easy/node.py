"""The easy part of a node: cards + items -> a node record, plus views, scoring and the prerequisite test.

A compiled item has:
- question: safe before the answer (inside GET /nodes/{id})
- reveal:   only after the answer (POST /answers)
- meta:     internal
"""
from __future__ import annotations

import datetime as dt
import random
import re

from common import AttemptError, Report, as_date, check_source_ids, is_text, localize_all

from .kinds import ITEM_KINDS, SCORED

NODE_RE = re.compile(r"^[A-Z][0-9]+$")
MAX_CARD_WORDS = 80
PASS_AVERAGE = 0.8  # spec: the easy part is done when the items average at least this
MEDIUM_PASS = 0.6   # spec: plus one medium task with at least this score


# ---------------------------------------------------------------- validate

def _check_valid_until(owner: str, obj: dict, today: dt.date, r: Report):
    if "valid_until" in obj:
        until = as_date(obj["valid_until"])
        if until is None:
            r.error(f"{owner}: valid_until must be a date")
        elif until < today:
            r.error(f"{owner}: valid_until {until} is in the past")


def validate_card(card: dict, node: str, sources: dict, today: dt.date, r: Report):
    cid = card.get("id")
    if not isinstance(cid, str) or not re.match(rf"^{node.lower()}\.c[0-9]+$", cid):
        r.error(f"card id {cid!r} must look like {node.lower()}.c<n>")
    for key in ("title", "body"):
        if not is_text(card.get(key)):
            r.error(f"{cid}: {key} is required")
    if is_text(card.get("body")):
        words = max(len(s.split()) for s in ([card["body"]] if isinstance(card["body"], str) else card["body"].values()))
        if words > MAX_CARD_WORDS:
            r.error(f"{cid}: body has {words} words (at most {MAX_CARD_WORDS})")
    if not is_text(card.get("example")):
        r.warn(f"{cid}: no example")
    links = card.get("links", [])
    check_source_ids(cid, links, sources, r, "links")
    if isinstance(links, list) and not 1 <= len(links) <= 2:
        r.warn(f"{cid}: {len(links)} links (the spec asks for 1-2)")
    if card.get("figure") is not None:
        r.warn(f"{cid}: figure is not rendered yet")
    _check_valid_until(cid, card, today, r)


def validate_item(item: dict, node: str, sources: dict, today: dt.date, r: Report):
    iid = item.get("id")
    if not isinstance(iid, str) or not re.match(rf"^{node.lower()}\.e[0-9]+$", iid):
        r.error(f"item id {iid!r} must look like {node.lower()}.e<n>")
    kind = item.get("kind")
    if kind not in ITEM_KINDS:
        r.error(f"{iid}: kind {kind!r} must be one of {sorted(ITEM_KINDS)}")
        return
    if not is_text(item.get("q")):
        r.error(f"{iid}: q is required")
    ITEM_KINDS[kind].validate(item, r)
    if kind in SCORED and not is_text(item.get("why")):
        r.error(f"{iid}: why is required (shown after the answer)")
    if not isinstance(item.get("check", False), bool):
        r.error(f"{iid}: check must be true or false")
    if item.get("check") and kind not in SCORED:
        r.error(f"{iid}: a reflection can't be a check item (it is not scored)")
    if not isinstance(item.get("difficulty", 0.0), (int, float)) or isinstance(item.get("difficulty"), bool):
        r.error(f"{iid}: difficulty must be a number (starting Elo difficulty)")
    cv = item.get("content_version", 1)
    if not isinstance(cv, int) or isinstance(cv, bool) or cv < 1:
        r.error(f"{iid}: content_version must be a positive integer")
    check_source_ids(iid, item.get("sources", []), sources, r, "sources")
    _check_valid_until(iid, item, today, r)


def validate_node(data: dict, sources: dict, today: dt.date) -> Report:
    r = Report()
    node = data.get("node")
    if not isinstance(node, str) or not NODE_RE.match(node):
        r.error(f"node {node!r} must look like I4 (panel letter + number)")
        return r
    for key in ("panel", "title"):
        if not is_text(data.get(key)):
            r.error(f"{node}: {key} is required")
    after = data.get("after", [])
    if not isinstance(after, list) or not all(isinstance(a, str) for a in after):
        r.error(f"{node}: after must be a list of node ids")
    if not data.get("reviewer"):
        r.warn(f"{node}: no reviewer yet: the node must not go live")
    for card in data.get("cards") or []:
        validate_card(card, node, sources, today, r)
    for item in data.get("items") or []:
        validate_item(item, node, sources, today, r)
    return r


def graph_problems(nodes: dict[str, dict]) -> tuple[list[str], list[str]]:
    """(errors, warnings) for the prerequisite graph: unknown nodes are warnings, cycles are errors."""
    errors, warnings = [], []
    for nid, data in nodes.items():
        for a in data.get("after") or []:
            if a not in nodes:
                warnings.append(f"{nid}: prerequisite {a} has no node file yet")
    state: dict[str, int] = {}

    def visit(n: str, path: list[str]):
        state[n] = 1
        for a in nodes[n].get("after") or []:
            if a not in nodes:
                continue
            if state.get(a) == 1:
                errors.append("prerequisite cycle: " + " -> ".join(path + [n, a]))
            elif a not in state:
                visit(a, path + [n])
        state[n] = 2

    for n in nodes:
        if n not in state:
            visit(n, [])
    return errors, warnings


# ---------------------------------------------------------------- compile

def _link(sid: str, sources: dict) -> dict:
    s = sources.get(sid, {})
    return {"id": sid, "title": s.get("title"), "publisher": s.get("publisher"), "url": s.get("url")}


def compile_item(item: dict, node: str) -> dict:
    kind = ITEM_KINDS[item["kind"]]
    scored = item["kind"] in SCORED
    question = {"kind": item["kind"], "q": item["q"], **kind.public(item)}
    if scored:
        question["confidence"] = {"min": 1, "max": 5}
    return {
        "id": item["id"],
        "node": node,
        "level": "easy",
        "kind": item["kind"],
        "content_version": item.get("content_version", 1),
        "check": bool(item.get("check", False)),
        "scored": scored,
        "difficulty": float(item.get("difficulty", 0.0)),
        "question": question,
        "reveal": {**kind.reveal(item), "why": item.get("why"), "sources": item.get("sources", [])},
        "meta": {"secrets": kind.secrets(item)},
    }


def compile_node(data: dict, sources: dict, file: str | None = None) -> dict:
    node = data["node"]
    cards = []
    for c in data.get("cards") or []:
        card = {k: c[k] for k in ("id", "title", "body", "example") if k in c}
        card["links"] = [_link(sid, sources) for sid in c.get("links", [])]
        if "valid_until" in c:
            card["valid_until"] = str(c["valid_until"])
        cards.append(card)
    return {
        "node": node,
        "panel": data["panel"],
        "title": data["title"],
        "after": data.get("after", []),
        "status": data.get("status", "draft"),
        "live": bool(data.get("reviewer")),
        "cards": cards,
        "items": [compile_item(i, node) for i in data.get("items") or []],
        "meta": {"content_file": file, "author": data.get("author"), "reviewer": data.get("reviewer"),
                 "checked": {c["id"]: c["checked"] for c in data.get("cards") or [] if c.get("checked")}},
    }


# ---------------------------------------------------------------- views

def node_view(node: dict, lang: str = "en") -> dict:
    """GET /nodes/{id}: the node's cards and items, without answers."""
    out = {k: node[k] for k in ("node", "panel", "title", "after", "status")}
    out["cards"] = localize_all(node["cards"], lang)
    out["items"] = [question_view(i, lang) for i in node["items"]]
    return localize_all(out, lang)


def question_view(item: dict, lang: str = "en") -> dict:
    base = {k: item[k] for k in ("id", "node", "level", "kind", "content_version", "scored")}
    return {**base, **localize_all(item["question"], lang)}


def reveal_view(item: dict, lang: str = "en") -> dict:
    return localize_all(item["reveal"], lang)


def secrets(item: dict) -> dict:
    """For the tutor's ContextProvider.task_secrets(): answer texts and numbers it must not reveal."""
    return {"strings": list(item["meta"]["secrets"]["strings"]), "numbers": list(item["meta"]["secrets"]["numbers"])}


# ---------------------------------------------------------------- score

def score(item: dict, response, confidence: int | None = None) -> dict:
    """Score one answer. Field names match the attempt record in docs/task_engines.md."""
    kind = ITEM_KINDS[item["kind"]]
    # The kinds read the authored fields; rebuild them from the compiled record.
    authored = {**item["question"], **item["reveal"]}
    err = kind.check(authored, response)
    if err:
        raise AttemptError(f"{item['id']}: {err}")
    if confidence is not None and (isinstance(confidence, bool) or confidence not in range(1, 6)):
        raise AttemptError("confidence must be an integer from 1 to 5")
    value = kind.score(authored, response)
    return {
        "task_id": item["id"],
        "content_version": item["content_version"],
        "level": "easy",
        "response": {"value": response},
        "confidence": confidence if item["scored"] else None,
        "p": None if confidence is None or not item["scored"] else (confidence - 1) / 4,
        "score_estimate": None,   # medium-engine columns of the attempt record; unused for easy items
        "score_reasons": None,
        "score": None if value is None else round(value, 4),
    }


# ---------------------------------------------------------------- prerequisite test and completion

def prerequisite_pool(nodes: dict[str, dict], node_id: str) -> list[dict]:
    """Check items of the node's prerequisite nodes, in file order."""
    pool = []
    for pre in nodes[node_id].get("after", []):
        if pre in nodes:
            pool += [i for i in nodes[pre]["items"] if i["check"]]
    return pool


def prerequisite_test(nodes: dict[str, dict], node_id: str, seed: int | str, n: int = 3) -> list[str]:
    """2-3 check items from the prerequisite nodes, spread across them. The same seed gives the same test.

    Use e.g. the user id as the seed, so a reload shows the same test.
    """
    rng = random.Random(f"{seed}:{node_id}")
    by_node: dict[str, list[str]] = {}
    for item in prerequisite_pool(nodes, node_id):
        by_node.setdefault(item["node"], []).append(item["id"])
    for ids in by_node.values():
        rng.shuffle(ids)
    order = sorted(by_node)
    rng.shuffle(order)
    picked: list[str] = []
    while len(picked) < n and any(by_node.values()):  # round robin over the prerequisite nodes
        for pre in order:
            if by_node[pre] and len(picked) < n:
                picked.append(by_node[pre].pop())
    return picked


def test_out(nodes: dict[str, dict], node_id: str, seed: int | str, n: int = 2) -> list[str]:
    """2 of the node's own check items, for a node the router marks "probably known"
    (docs/onboarding_router.md, "Path"). The same seed gives the same items."""
    ids = [i["id"] for i in nodes[node_id]["items"] if i["check"]]
    random.Random(f"{seed}:{node_id}:test_out").shuffle(ids)
    return ids[:n]


def prerequisite_passed(scores: list[float]) -> bool:
    """Passing means every drawn item scored 1. Used for test-outs too."""
    return bool(scores) and all(s == 1 for s in scores)


def easy_done(prerequisite_scores: list[float], item_scores: list[float]) -> bool:
    """The node's easy part is done when the prerequisite test was passed, or the items average >= 0.8."""
    if prerequisite_passed(prerequisite_scores):
        return True
    return bool(item_scores) and sum(item_scores) / len(item_scores) >= PASS_AVERAGE


def node_done(easy_part_done: bool, medium_scores: list[float], test_out_scores: list[float] = ()) -> bool:
    """Spec, "Node completion": the easy part is done and one medium task scored at least 0.6.
    A passed test-out (the "challenge") completes the whole node on its own (decided 2026-11-21).
    Hard tasks are optional for completion."""
    if prerequisite_passed(list(test_out_scores)):
        return True
    return easy_part_done and any(s >= MEDIUM_PASS for s in medium_scores)
