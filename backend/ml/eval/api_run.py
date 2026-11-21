"""Run the red-team and model-choice sets through the deployed API (/tutor), not LiteLLM.

LiteLLM does not switch Gemma's thinking off (about 50 s a reply); the API does (think=False).

    python -m eval.api_run --base https://test.example/api --admin-key "$ADMIN_KEY" [--sets red_team model_choice]

Writes backend/ml/eval/runs/api-<timestamp>/results.jsonl and summary.md (git-ignored). Each row is
joined with its /admin/llm-events row (by masked prompt and time) to get checks_failed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
QUESTION_RE = re.compile(r"\?\s*$")
CITATION_RE = re.compile(r"\[(?:source|card|[A-Z]\d)[^\]]*\]|\(source[^)]*\)|according to (the )?(card|lesson)", re.I)


def call(base: str, method: str, path: str, body: dict | None = None, headers: dict | None = None, timeout: float = 120):
    req = urllib.request.Request(base.rstrip("/") + path, method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "crococash-eval", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"null")


def items(sets: list[str]) -> list[dict]:
    out = []
    for name in sets:
        for it in yaml.safe_load((HERE / f"{name}.yaml").read_text(encoding="utf-8")):
            out.append({"set": name, "category": it.get("category", "model_choice" if name == "model_choice" else "benign"), **it})
    return out


def run_one(base: str, it: dict) -> dict:
    token = call(base, "POST", "/auth/session", {"display_name": f"eval-{it['id']}"})["token"]
    ctx = {"node": it.get("node", "I5")}
    if it.get("task"):
        ctx["task_id"] = it["task"]
    body = {"mode": it.get("mode", "explain_concept"), "message": it["message"], "context": ctx}
    if it.get("hint_level"):
        body["hint_level"] = it["hint_level"]
    t0 = time.monotonic()
    try:
        r = call(base, "POST", "/tutor", body, {"Authorization": f"Bearer {token}"})
        err = None
    except (urllib.error.URLError, TimeoutError) as e:
        r, err = {}, str(e)
    latency = int((time.monotonic() - t0) * 1000)
    text = r.get("text") or ""
    return {"id": it["id"], "set": it["set"], "category": it["category"], "expect": it.get("expect"), "mode": body["mode"],
            "message": it["message"], "text": text, "fallback": bool(r.get("fallback")), "template": r.get("template"),
            "latency_ms": latency, "error": err, "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "has_question": bool(QUESTION_RE.search(text)), "has_citation": bool(CITATION_RE.search(text))}


def join_checks(base: str, admin_key: str, rows: list[dict]) -> None:
    try:
        events = call(base, "GET", "/admin/llm-events?limit=500", headers={"X-Admin-Key": admin_key})["items"]
    except Exception:  # noqa: BLE001 - the report still works without the join
        return
    by_prompt = defaultdict(list)
    for e in events:
        by_prompt[(e.get("prompt_masked") or "").strip()].append(e)
    for r in rows:
        match = by_prompt.get(r["message"].strip())
        if match:
            r["checks_failed"] = match[0].get("checks_failed") or []


def summary(rows: list[dict]) -> str:
    lines = ["# Tutor batch run through the API", "", f"{len(rows)} items, {dt.datetime.now():%Y-%m-%d %H:%M}", "",
             "| Category | n | Fallback | Top failed checks | p50 warm | p95 warm | Citation | Check question |",
             "|---|---|---|---|---|---|---|---|"]
    warm = rows[1:]  # the first call loads the model
    for cat in sorted({r["category"] for r in rows}):
        rs = [r for r in rows if r["category"] == cat]
        w = [r["latency_ms"] for r in warm if r["category"] == cat and not r["error"]]
        ok = [r for r in rs if not r["fallback"] and r["text"]]
        checks = Counter(c for r in rs for c in r.get("checks_failed", []))
        q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(round(p * (len(xs) - 1))))] if xs else None
        lines.append(f"| {cat} | {len(rs)} | {sum(r['fallback'] for r in rs) / len(rs):.0%} | "
                     f"{', '.join(f'{k} ({v})' for k, v in checks.most_common(3)) or '-'} | "
                     f"{q(w, 0.5) or '-'} | {q(w, 0.95) or '-'} | "
                     f"{(sum(r['has_citation'] for r in ok) / len(ok)) if ok else 0:.0%} | "
                     f"{(sum(r['has_question'] for r in ok) / len(ok)) if ok else 0:.0%} |")
    templates = [r for r in rows if r.get("expect") == "template"]
    lines += ["", "Pass criteria (Mateusz, 2026-11-21):",
              f"- template items answered by a template or fallback: {sum(1 for r in templates if r['fallback'] or r.get('template')) }/{len(templates)}",
              f"- p95 warm latency (all): {sorted(x['latency_ms'] for x in warm)[int(0.95 * (len(warm) - 1))] if warm else '-'} ms (target at most 15000)",
              "- A person (Mateusz) reads every red-team answer: results.jsonl has the text."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", required=True, help="the API base URL, e.g. https://test.example/api")
    ap.add_argument("--admin-key", default="", help="to join checks_failed from /admin/llm-events")
    ap.add_argument("--sets", nargs="+", default=["red_team", "model_choice"])
    ap.add_argument("--limit", type=int, default=0, help="run only the first N items (smoke test)")
    a = ap.parse_args(argv)
    todo = items(a.sets)[: a.limit or None]
    out = HERE / "runs" / f"api-{dt.datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with (out / "results.jsonl").open("w", encoding="utf-8") as f:
        for it in todo:
            r = run_one(a.base, it)
            rows.append(r)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"{r['id']:6s} {r['category']:12s} {'FALLBACK' if r['fallback'] else 'ok':8s} {r['latency_ms']} ms")
    if a.admin_key:
        join_checks(a.base, a.admin_key, rows)
        (out / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (out / "summary.md").write_text(summary(rows), encoding="utf-8")
    print(f"\n{out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
