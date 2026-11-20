"""Knowledge base: ingest reviewed passages from backend/content, and search them.

Passages are our own words (cards from nodes/*.yaml, later kb/<node>/*.md). Ingestion rejects a
passage that is unreviewed, expired, too long, or whose source is unknown or not licence-checked.
In production the accepted passages go to the kb_chunks table and `SEARCH_SQL` runs on Postgres;
`search` below is the same ranking idea in memory, for development and tests.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml

CONTENT = Path(__file__).resolve().parents[2] / "content"
MAX_WORDS = 150

SEARCH_SQL = """
select chunk_id, body, url, source_id, ts_rank(tsv, plainto_tsquery('english', %(query)s)) as rank
from kb_chunks
where node_ids && %(nodes)s::text[] and (valid_until is null or valid_until >= current_date)
order by (%(node)s = any(node_ids)) desc, rank desc
limit %(k)s
"""


def _read_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_sources(content: Path = CONTENT) -> dict[str, dict]:
    return {s["id"]: s for s in _read_yaml(content / "sources.yaml")}


def load_nodes(content: Path = CONTENT) -> dict[str, dict]:
    nodes = {}
    for path in sorted((content / "nodes").glob("*.yaml")):
        if not path.name.startswith("_"):
            data = _read_yaml(path) or {}
            nodes[data["node"]] = data
    return nodes


def passages_from_cards(nodes: dict[str, dict], sources: dict[str, dict]) -> list[dict]:
    out = []
    for node_id, node in nodes.items():
        for card in node.get("cards") or []:
            links = card.get("links") or []
            text = " ".join(x for x in [card.get("title", "") + ".", card["body"], card.get("example", "")] if x)
            out.append({
                "chunk_id": card["id"],
                "node_ids": [node_id],
                "source_ids": links,
                "url": sources.get(links[0], {}).get("url") if links else None,
                "body": text,
                "valid_until": card.get("valid_until"),
                "reviewed_by": node.get("reviewer"),
            })
    return out


def problems(p: dict, sources: dict[str, dict], today: dt.date) -> list[str]:
    out = []
    if not p.get("reviewed_by"):
        out.append("not reviewed")
    for sid in p["source_ids"]:
        if sid not in sources:
            out.append(f"unknown source {sid}")
        elif sources[sid].get("licence", "to_check").startswith("to_check"):
            out.append(f"licence of {sid} not checked")
    until = p.get("valid_until")
    if until and dt.date.fromisoformat(str(until)) < today:
        out.append(f"expired {until}")
    if len(p["body"].split()) > MAX_WORDS:
        out.append(f"longer than {MAX_WORDS} words")
    return out


def ingest(content: Path = CONTENT, today: dt.date | None = None) -> tuple[list[dict], dict[str, list[str]]]:
    """Return (accepted passages, {chunk_id: problems} for rejected ones)."""
    today = today or dt.date.today()
    sources = load_sources(content)
    accepted, rejected = [], {}
    for p in passages_from_cards(load_nodes(content), sources):
        errs = problems(p, sources, today)
        if errs:
            rejected[p["chunk_id"]] = errs
        else:
            accepted.append(p)
    return accepted, rejected


_WORD = re.compile(r"[a-z0-9]+")
STOP = set("a an and are as at be by for from has have how i if in is it its of on or that the this to was what when "
           "which why with you your".split())


def _terms(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in STOP and len(w) > 2}


def search(passages: list[dict], node: str, query: str, k: int, prerequisites: dict[str, list[str]]) -> list[dict]:
    """The node's own passages first, then its prerequisites'; within each group by term overlap."""
    allowed = [node] + list(prerequisites.get(node, []))
    q = _terms(query)
    pool = [p for p in passages if set(p["node_ids"]) & set(allowed)]
    ranked = sorted(pool, key=lambda p: (node not in p["node_ids"], -len(q & _terms(p["body"]))))
    return ranked[:k]
