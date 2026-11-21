"""Build medium tasks: backend/content/nodes/*.yaml -> output/medium_tasks.json + output/medium_qa.md.

    cd backend/data
    python -m medium.build             # all medium tasks
    python -m medium.build --only d1.m1
    python -m medium.build --strict    # exit 1 if any task has an error

Medium tasks are listed under `medium:` in each node file (node: D1 / medium: [ {id: d1.m1, ...} ]). A task with an error is left out of the output.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import load_nodes, load_sources

from .parts import Report
from .series import DataError, SeriesStore
from .task import compile_task, validate

DATA = Path(__file__).resolve().parent.parent
NODES = DATA.parent / "content" / "nodes"
SERIES = DATA / "series"
OUT = DATA / "output"
SCHEMA_VERSION = 1


def load_tasks(nodes_dir: Path) -> list[dict]:
    """The tasks under `medium:` in every node file."""
    tasks = []
    for name, data in load_nodes(nodes_dir):
        for t in data.get("medium") or []:
            if isinstance(t, dict):
                tasks.append({"node": data.get("node"), "level": "medium", **t, "_file": name})
    return tasks


def build(nodes_dir: Path = NODES, series_dir: Path = SERIES, only: list[str] | None = None):
    """Returns [(task_id, record or None, Report)]."""
    store = SeriesStore(series_dir)
    sources = load_sources(nodes_dir.parent)
    results, seen = [], set()
    for task in load_tasks(nodes_dir):
        tid = task.get("id")
        if only and tid not in only:
            continue
        r = validate(task, store, sources=sources)
        if tid in seen:
            r.error(f"duplicate id {tid!r}")
        seen.add(tid)
        record = None
        if not r.errors:
            try:
                record = compile_task(task, store, r)
            except DataError as e:
                r.error(f"data: {e}")
        results.append((str(tid), None if r.errors else record, r, task.get("_file")))
    return results


def qa_report(results) -> str:
    ok = sum(1 for _, rec, r, _ in results if rec and not r.warnings)
    warn = sum(1 for _, rec, r, _ in results if rec and r.warnings)
    bad = sum(1 for _, rec, _, _ in results if not rec)
    lines = ["# Medium tasks: QA report", "",
             f"Tasks: {len(results)} · ✅ {ok} · ⚠️ {warn} · ❌ {bad} (❌ tasks are left out of medium_tasks.json)", "",
             "| | id | variant | outcome | data |", "|---|---|---|---|---|"]
    for tid, rec, r, _ in results:
        mark = "❌" if not rec else "⚠️" if r.warnings else "✅"
        out, data = "", ""
        if rec:
            o = rec["reveal"]["outcome"]
            out = f"{o['direction']} ({o['change']:+g} {o['unit']})" if o else ""
            data = "synthetic" if rec["meta"]["synthetic"] else ", ".join(a["source"] for a in rec["meta"]["attribution"])
        lines.append(f"| {mark} | {tid} | {rec['variant'] if rec else ''} | {out} | {data} |")
    for tid, rec, r, file in results:
        if r.errors or r.warnings:
            lines += ["", f"## {tid} ({file})"]
            lines += [f"- ❌ {e}" for e in r.errors] + [f"- ⚠️ {w}" for w in r.warnings]
    return "\n".join(lines) + "\n"


def write(results, out_dir: Path = OUT) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "medium_tasks.json"
    payload = {"schema_version": SCHEMA_VERSION, "tasks": [rec for _, rec, _, _ in results if rec]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "medium_qa.md").write_text(qa_report(results), encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build medium tasks.")
    ap.add_argument("--nodes", type=Path, default=NODES)
    ap.add_argument("--series", type=Path, default=SERIES)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--only", nargs="+", metavar="ID")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    results = build(args.nodes, args.series, args.only)
    path = write(results, args.out)
    bad = [(tid, r) for tid, rec, r, _ in results if not rec]
    print(f"{len(results) - len(bad)}/{len(results)} tasks -> {path}")
    print(f"QA report: {args.out / 'medium_qa.md'}")
    for tid, r in bad:
        print(f"  ❌ {tid}: {r.errors[0]}", file=sys.stderr)
    return 1 if args.strict and bad else 0


if __name__ == "__main__":
    sys.exit(main())
