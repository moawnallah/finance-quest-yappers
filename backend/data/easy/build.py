"""Build the easy part of every node: backend/content/nodes/*.yaml -> output/easy.json + output/easy_qa.md.

    cd backend/data
    python -m easy.build             # all nodes
    python -m easy.build --strict    # exit 1 if any node has an error

A node with an error is left out of the output (with all its cards and items).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from common import load_nodes, load_sources

from .node import compile_node, graph_problems, prerequisite_pool, validate_node

DATA = Path(__file__).resolve().parent.parent
CONTENT = DATA.parent / "content"
OUT = DATA / "output"
SCHEMA_VERSION = 1


def build(content: Path = CONTENT, today: dt.date | None = None):
    """Returns (records {node: record}, reports {node: Report}, graph_errors, graph_warnings)."""
    today = today or dt.date.today()
    sources = load_sources(content)
    raw: dict[str, tuple[str, dict]] = {}
    reports = {}
    for name, data in load_nodes(content / "nodes"):
        node = str(data.get("node"))
        r = validate_node(data, sources, today)
        if node in raw:
            r.error(f"duplicate node {node} (also in {raw[node][0]})")
        raw.setdefault(node, (name, data))
        reports[node] = r
    seen: dict[str, str] = {}
    for node, (_, data) in raw.items():
        for x in (data.get("cards") or []) + (data.get("items") or []):
            xid = x.get("id")
            if xid in seen:
                reports[node].error(f"duplicate id {xid!r} (also in {seen[xid]})")
            seen.setdefault(xid, node)

    graph_errors, graph_warnings = graph_problems({n: d for n, (_, d) in raw.items()})
    records = {n: compile_node(d, sources, name) for n, (name, d) in raw.items() if not reports[n].errors}
    if graph_errors:
        records = {}
    return records, reports, graph_errors, graph_warnings


def qa_report(records, reports, graph_errors, graph_warnings) -> str:
    ok = sum(1 for n in reports if n in records and not reports[n].warnings)
    warn = sum(1 for n in reports if n in records and reports[n].warnings)
    bad = sum(1 for n in reports if n not in records)
    lines = ["# Easy part of the nodes: QA report", "",
             f"Nodes: {len(reports)} · ✅ {ok} · ⚠️ {warn} · ❌ {bad} (❌ nodes are left out of easy.json)", "",
             "| | node | cards | items | check items | prerequisite pool |", "|---|---|---|---|---|---|"]
    for n in sorted(reports):
        rec = records.get(n)
        mark = "❌" if rec is None else "⚠️" if reports[n].warnings else "✅"
        if rec:
            checks = sum(1 for i in rec["items"] if i["check"])
            pool = len(prerequisite_pool(records, n)) if rec["after"] else "-"
            lines.append(f"| {mark} | {n} | {len(rec['cards'])} | {len(rec['items'])} | {checks} | {pool} |")
        else:
            lines.append(f"| {mark} | {n} | | | | |")
    if graph_errors or graph_warnings:
        lines += ["", "## Prerequisite graph"] + [f"- ❌ {e}" for e in graph_errors] + [f"- ⚠️ {w}" for w in graph_warnings]
    for n in sorted(reports):
        r = reports[n]
        if r.errors or r.warnings:
            lines += ["", f"## {n}"] + [f"- ❌ {e}" for e in r.errors] + [f"- ⚠️ {w}" for w in r.warnings]
    return "\n".join(lines) + "\n"


def write(records, reports, graph_errors, graph_warnings, out_dir: Path = OUT) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "easy.json"
    payload = {"schema_version": SCHEMA_VERSION, "nodes": [records[n] for n in sorted(records)]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "easy_qa.md").write_text(qa_report(records, reports, graph_errors, graph_warnings), encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the easy part of every node.")
    ap.add_argument("--content", type=Path, default=CONTENT)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    records, reports, graph_errors, graph_warnings = build(args.content)
    path = write(records, reports, graph_errors, graph_warnings, args.out)
    items = sum(len(r["items"]) for r in records.values())
    print(f"{len(records)}/{len(reports)} nodes, {items} items -> {path}")
    print(f"QA report: {args.out / 'easy_qa.md'}")
    for e in graph_errors:
        print(f"  ❌ {e}", file=sys.stderr)
    for n, r in sorted(reports.items()):
        if r.errors:
            print(f"  ❌ {n}: {r.errors[0]}", file=sys.stderr)
    return 1 if args.strict and (graph_errors or len(records) < len(reports)) else 0


if __name__ == "__main__":
    sys.exit(main())
