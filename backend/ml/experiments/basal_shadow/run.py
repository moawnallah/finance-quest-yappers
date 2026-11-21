"""BASAL in shadow mode: agreement and stability against the router on the test personas.

    BASAL_URL=http://127.0.0.1:8011 python -m experiments.basal_shadow.run

About 30 requests: the four personas in tests/test_router.py, plus perturbations (shuffled candidates,
the goal reworded, a field that should not matter changed, with_router=False). Measures agreement and
stability only; which of the two is better needs real first-item outcomes, so no claim about that.
Writes experiments/basal_shadow/runs/<run-id>/results.jsonl and summary.md (git-ignored).
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import random
import statistics
from pathlib import Path

from router import route, shadow
from tests.test_router import INVESTOR, RETIREE, STUDENT, YOUNG

HERE = Path(__file__).resolve().parent
PERSONAS = {"young": YOUNG, "investor": INVESTOR, "student": STUDENT, "retiree": RETIREE}
GOAL_REWORD = {"first_investment": "other", "other": "first_investment", "buffer": "home", "retirement": "other"}


def variants(name: str, survey: dict) -> list[tuple[str, dict, dict]]:
    """(label, survey, build_request options) for one persona."""
    out = [("base", survey, {})]
    out.append(("shuffled", survey, {"shuffle": True}))
    out.append(("goal_reworded", {**survey, "goal": GOAL_REWORD.get(survey["goal"], "other")}, {}))
    out.append(("irrelevant_field", {**survey, "decisions": "with_someone" if survey.get("decisions") != "with_someone" else "me"}, {}))
    out.append(("no_router", survey, {"with_router": False}))
    out.append(("shuffled_2", survey, {"shuffle": True, "seed": 2}))
    out.append(("base_repeat", survey, {}))
    return out


def request_for(survey: dict, result: dict, opts: dict) -> dict:
    req = shadow.build_request(survey, result, **({"with_router": opts["with_router"]} if "with_router" in opts else {}))
    if opts.get("shuffle"):  # same content, different order of candidates and questions
        req = copy.deepcopy(req)
        rng = random.Random(opts.get("seed", 1))
        rng.shuffle(req["state"]["candidates"])
        items = list(req["questions"].items())
        rng.shuffle(items)
        req["questions"] = dict(items)
    return req


def main() -> int:
    base = os.getenv("BASAL_URL")
    if not base:
        raise SystemExit("Set BASAL_URL (for example http://127.0.0.1:8011)")
    run = HERE / "runs" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    rows, lat = [], []
    for name, survey in PERSONAS.items():
        result = route(survey, f"persona-{name}")
        for label, sv, opts in variants(name, survey):
            res = route(sv, f"persona-{name}") if sv is not survey else result
            try:
                resp, ms = shadow.ask(request_for(sv, res, opts), base, timeout=30)
                lat.append(ms)
                dec = shadow.compare(res, resp)
                rows.append({"persona": name, "variant": label, "latency_ms": ms, "model": resp.get("model"), "decisions": dec})
            except Exception as e:  # noqa: BLE001
                rows.append({"persona": name, "variant": label, "error": f"{type(e).__name__}: {e}"[:200]})
            print(f"{name:9s} {label:17s} {'error' if 'error' in rows[-1] else str(rows[-1]['latency_ms']) + ' ms'}")
    (run / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    ok = [r for r in rows if "error" not in r]
    dec = [d for r in ok for d in r["decisions"]]
    agree = [d["agrees"] for d in dec if isinstance(d.get("agrees"), bool)]
    pairs = [(d["router_m"], d["ready_p"]) for d in dec if isinstance(d.get("router_m"), (int, float)) and isinstance(d.get("ready_p"), (int, float))]
    corr = statistics.correlation(*zip(*pairs)) if len(pairs) > 2 else None
    flips = 0
    for name in PERSONAS:
        b = next((r for r in ok if r["persona"] == name and r["variant"] == "base"), None)
        if not b:
            continue
        base_start = {d["node"]: (d.get("start_p") or 0) >= 0.5 for d in b["decisions"]}
        for r in ok:
            if r["persona"] == name and r["variant"] in ("shuffled", "shuffled_2", "irrelevant_field", "base_repeat"):
                flips += sum(1 for d in r["decisions"] if d["node"] in base_start and ((d.get("start_p") or 0) >= 0.5) != base_start[d["node"]])
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(round(p * (len(xs) - 1))))] if xs else None
    md = ["# BASAL shadow measurement", "", f"{len(rows)} requests, {len(rows) - len(ok)} errors, model {ok[0]['model'] if ok else '-'}", "",
          f"- agreement with the router's path: {sum(agree) / len(agree):.0%}" if agree else "- agreement: no decisions",
          f"- correlation of ready_p with the router's mastery: {corr:.2f}" if corr is not None else "- correlation: not enough pairs",
          f"- decision flips under perturbations that should not matter: {flips}",
          f"- share below tau: {sum(1 for d in dec if d.get('below_tau')) / len(dec):.0%}" if dec else "- share below tau: -",
          f"- latency p50 {q(lat, 0.5)} ms, p95 {q(lat, 0.95)} ms",
          "", "Agreement and stability only; which is better needs real first-item outcomes."]
    (run / "summary.md").write_text("\n".join(md) + "\n")
    print("\n" + "\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
