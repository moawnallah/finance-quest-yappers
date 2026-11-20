"""Build hard tasks: backend/content/nodes/*.yaml (`hard:` lists) -> output/hard_tasks.json + output/hard_qa.md.

    cd backend/data
    python -m hard.build             # all hard tasks
    python -m hard.build --strict    # exit 1 if any task has an error

The build runs the golden checks: the reference program must be accepted, and every known-bad
program must fail the test it names. A task with an error is left out of the output.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import load_nodes, load_sources

from .task import compile_task, validate

DATA = Path(__file__).resolve().parent.parent
CONTENT = DATA.parent / "content"
OUT = DATA / "output"
SCHEMA_VERSION = 1


def load_tasks(content: Path = CONTENT) -> list[dict]:
    tasks = []
    for fname, data in load_nodes(content / "nodes"):
        for t in data.get("hard") or []:
            if isinstance(t, dict):
                tasks.append({"node": data.get("node"), **t, "_file": fname})
    return tasks


def build(content: Path = CONTENT):
    """Returns [(task_id, record or None, Report, file)]."""
    sources = load_sources(content)
    results, seen = [], set()
    for task in load_tasks(content):
        r = validate(task, sources)
        if task.get("id") in seen:
            r.error(f"duplicate id {task.get('id')!r}")
        seen.add(task.get("id"))
        record = None if r.errors else compile_task(task)
        results.append((str(task.get("id")), record, r, task.get("_file")))
    return results


def qa_report(results) -> str:
    lines = ["# Hard tasks: QA report", "", "| | id | reference score | bots |", "|---|---|---|---|"]
    for tid, rec, r, _ in results:
        mark = "❌" if not rec else "⚠️" if r.warnings else "✅"
        bots = ", ".join(f"{b['name']}: {b['score'] if b['accepted'] else 'not accepted'}" for b in rec["question"]["bots"]) if rec else ""
        lines.append(f"| {mark} | {tid} | {'' if not rec else 'ok'} | {bots} |")
    for tid, rec, r, file in results:
        if r.errors or r.warnings:
            lines += ["", f"## {tid} ({file})"] + [f"- ❌ {e}" for e in r.errors] + [f"- ⚠️ {w}" for w in r.warnings]
    return "\n".join(lines) + "\n"


def write(results, out_dir: Path = OUT) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "hard_tasks.json"
    payload = {"schema_version": SCHEMA_VERSION, "tasks": [rec for _, rec, _, _ in results if rec]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "hard_qa.md").write_text(qa_report(results), encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build hard tasks.")
    ap.add_argument("--content", type=Path, default=CONTENT)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    results = build(args.content)
    path = write(results, args.out)
    bad = [(tid, r) for tid, rec, r, _ in results if not rec]
    print(f"{len(results) - len(bad)}/{len(results)} hard tasks -> {path}")
    for tid, r in bad:
        print(f"  ❌ {tid}: {r.errors[0]}", file=sys.stderr)
    return 1 if args.strict and bad else 0


if __name__ == "__main__":
    sys.exit(main())
