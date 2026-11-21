"""One hard task: validate -> compile -> (question_view, reveal_view, secrets) -> score.

The record has the same three blocks as the other engines (docs/architecture.md):
- question: safe before submission (brief, palette with sentence templates, starter program,
  visible test names, assumptions, baseline bots' scores);
- reveal: after submission (reference program, editorial, optional events and their weights);
- meta: internal (household, world, tests, futures settings, provenance). Never sent.
"""
from __future__ import annotations

import copy
import random
import statistics

from functools import lru_cache
from pathlib import Path

from common import AttemptError, Report, check_source_ids, is_text, localize_all
from series_store import SeriesStore
from sim import KINDS, Household, Scenario, build_path, metrics, run

from .blockly import ConversionError, block_definitions, program_to_workspace, toolbox, workspace_to_program
from .dsl import BLOCKS, VARS, check, compile_program

CHECKS = {"no_card_debt", "contributed_at_least", "net_worth_at_least", "weight_between", "weight_at_least"}
OVERRIDES = {"job_loss", "shocks", "price_rise", "returns", "trend"}
PASS_SCORE, MAX_SCORE = 51, 100


# ---------------------------------------------------------------- simulation helpers

def _household(spec: dict) -> Household:
    return Household(**spec["household"])


SERIES = Path(__file__).resolve().parent.parent / "series"


@lru_cache(maxsize=1)
def _store() -> SeriesStore:
    return SeriesStore(SERIES)


def _returns(world: dict, seed_offset: int = 0) -> dict[str, list[float]]:
    """Per-asset returns from a market path (docs/market_sim.md). world.market: {kind: synthetic |
    replay | bootstrap | fictional, ...}. With `asset` set, only that asset is the household's fund."""
    m = dict(world.get("market") or {"kind": "synthetic"})
    path = build_path(m, world["months"], seed_offset, _store())
    if m.get("asset"):
        return {m["asset"]: path.returns[m["asset"]]}
    return path.returns


def _scenario(world: dict, override: dict | None, returns: dict[str, list[float]]) -> Scenario:
    """A test's scenario: the base market path with the test's overrides applied.
    returns: {asset: {month: r}} sets single months; trend: [{asset, from, to, r}] sets a range."""
    o = override or {}
    returns = {a: list(r) for a, r in returns.items()}
    for asset, by_month in (o.get("returns") or {}).items():
        for month, r in by_month.items():
            returns[asset][int(month) - 1] = float(r)
    for t in o.get("trend") or []:
        for month in range(int(t["from"]), int(t["to"]) + 1):
            returns[t["asset"]][month - 1] = float(t["r"])
    return Scenario(months=world["months"], returns=returns,
                    job_loss=[tuple(x) for x in o.get("job_loss", [])],
                    shocks={int(k): float(v) for k, v in (o.get("shocks") or {}).items()},
                    price_rise=tuple(o["price_rise"]) if o.get("price_rise") else None)


def _weights(rows: list[dict], asset: str) -> list[float]:
    return [r["weights"].get(asset, 0.0) for r in rows]


def _passes(check_spec: dict, m: dict, rows: list[dict]) -> bool:
    ok = True
    if "weight_between" in check_spec:
        c = check_spec["weight_between"]
        ok &= all(c["low"] <= w <= c["high"] for w in _weights(rows, c["asset"]))
    if "weight_at_least" in check_spec:
        c = check_spec["weight_at_least"]
        ok &= all(w >= c["value"] for w in _weights(rows, c["asset"]))
    if check_spec.get("no_card_debt"):
        ok &= m["card_debt_max"] == 0
    if "contributed_at_least" in check_spec:
        ok &= m["contributed"] >= check_spec["contributed_at_least"]
    if "net_worth_at_least" in check_spec:
        ok &= m["net_worth_end"] >= check_spec["net_worth_at_least"]
    return bool(ok)


def _optional_metric(m: dict, rows: list[dict], spec: dict | None) -> float:
    """Default (card): 1 = never needed the card; 0.5 = needed it but repaid it; 0 = still in debt.
    band: 1 = the mix stayed in the band every month; 0.5 = out of it for at most 2 months; 0 = more."""
    if spec and "band" in spec:
        b = spec["band"]
        out = sum(1 for w in _weights(rows, b["asset"]) if not b["low"] <= w <= b["high"])
        return 1.0 if out == 0 else 0.5 if out <= 2 else 0.0
    if m["card_debt_max"] == 0:
        return 1.0
    return 0.5 if m["card_debt_end"] == 0 else 0.0


def _futures(meta: dict, policy) -> dict:
    f = meta["futures"]
    # Futures may run longer than the tests (e.g. 10 years), so growth differences show.
    world = {**meta["world"], "months": f.get("months", meta["world"]["months"])}
    rng = random.Random(f["seed"])
    clean, nets = 0, []
    for i in range(f["n"]):
        job_loss, shocks = [], {}
        for month in range(1, world["months"] + 1):
            if not job_loss and rng.random() < f["job_loss_per_month"]:
                job_loss.append((month, rng.randint(*f["job_loss_months"])))
            if rng.random() < f["shock_per_month"]:
                shocks[month] = round(rng.uniform(*f["shock_amount"]), -1)
        sc = Scenario(world["months"], _returns(world, 1000 + i), job_loss, shocks)
        m = metrics(run(_household(meta), policy, sc))
        clean += m["card_debt_max"] == 0
        nets.append(m["net_worth_end"])
    return {"n": f["n"], "without_card_debt": clean,
            "median_net_worth": round(statistics.median(nets), 2) if nets else None}


def evaluate(meta: dict, program: dict, with_futures: bool = True) -> dict:
    """Run a checked program through every test. The core of score(); also used by the build."""
    policy = compile_program(program)
    base_returns = _returns(meta["world"])
    obligatory, story = [], None
    for t in meta["obligatory"]:
        rows = run(_household(meta), policy, _scenario(meta["world"], t.get("override"), base_returns))
        passed = _passes(t["check"], metrics(rows), rows)
        obligatory.append({"name": t["name"], "passed": passed})
        if not passed and story is None:
            story = {"test": t["name"], "months": rows}
    accepted = all(t["passed"] for t in obligatory)
    optional, score = [], None
    if accepted:
        for t in meta["optional"]:
            rows = run(_household(meta), policy, _scenario(meta["world"], t.get("override"), base_returns))
            optional.append({"name": t["name"], "probability": t["probability"],
                             "metric": _optional_metric(metrics(rows), rows, meta.get("optional_metric"))})
        weight = sum(t["probability"] for t in optional)
        share = sum(t["probability"] * t["metric"] for t in optional) / weight if weight else 1.0
        score = round(PASS_SCORE + (MAX_SCORE - PASS_SCORE) * share)
    result = {"accepted": accepted, "score": score, "obligatory": obligatory, "optional": optional, "story": story}
    if accepted and with_futures:
        result["futures"] = _futures(meta, policy)
        ref = meta.get("reference_growth")
        med = result["futures"]["median_net_worth"]
        # Second axis (decided 2026-11-21): growth = median end net worth over the futures, as an
        # index where the reference solution = 100. Shown next to the 51-100 resilience points.
        result["growth_index"] = round(100 * med / ref, 1) if ref and med is not None else None
    return result


# ---------------------------------------------------------------- validate

def validate(task: dict, sources: dict) -> Report:
    r = Report()
    node, tid = str(task.get("node", "")), task.get("id")
    if not isinstance(tid, str) or not tid.startswith(node.lower() + ".h"):
        r.error(f"id {tid!r} must be <node>.h<n> ({node.lower()}.h1)")
    if task.get("level") != "hard":
        r.error("level must be hard")
    if not isinstance(task.get("content_version"), int) or task["content_version"] < 1:
        r.error("content_version must be a positive integer")
    if not task.get("author"):
        r.error("author is required")
    if not task.get("reviewer"):
        r.warn("no reviewer yet: the task must not go live")
    check_source_ids(str(tid), task.get("sources", []), sources, r)
    for f in ("brief", "editorial"):
        if not is_text(task.get(f)):
            r.error(f"{f} is required")
    palette, allowed = task.get("palette") or [], task.get("vars") or []
    for b in palette:
        if b not in BLOCKS:
            r.error(f"palette: unknown block {b!r}")
    for v in allowed:
        if v not in VARS:
            r.error(f"vars: unknown value {v!r}")
    try:
        Household(**task.get("household", {}))
    except TypeError as e:
        r.error(f"household: {e}")
    world = task.get("world") or {}
    if not isinstance(world.get("months"), int) or world["months"] < 1:
        r.error("world.months must be a positive integer")
    market = world.get("market") or {}
    if market.get("kind", "synthetic") not in KINDS:
        r.error(f"world.market.kind must be one of {list(KINDS)}")
    elif market.get("kind") in ("replay", "bootstrap") and not market.get("series"):
        r.error("world.market: replay and bootstrap need `series: {asset: series_id}`")
    if not task.get("obligatory"):
        r.error("at least one obligatory test is required")
    for t in task.get("obligatory") or []:
        if not set(t.get("check") or {}) or not set(t["check"]) <= CHECKS:
            r.error(f"obligatory {t.get('name')!r}: check must use {sorted(CHECKS)}")
        if not set(t.get("override") or {}) <= OVERRIDES:
            r.error(f"obligatory {t.get('name')!r}: override keys must be {sorted(OVERRIDES)}")
    for t in task.get("optional") or []:
        p = t.get("probability")
        if not isinstance(p, (int, float)) or not 0 < p <= 1:
            r.error(f"optional {t.get('name')!r}: probability must be in (0, 1]")
        if not set(t.get("override") or {}) <= OVERRIDES:
            r.error(f"optional {t.get('name')!r}: override keys must be {sorted(OVERRIDES)}")
    limits = task.get("limits") or {}
    programs = {"reference_program": task.get("reference_program"), "starter_program": task.get("starter_program")}
    programs.update({f"known_bad {b.get('name')!r}": b.get("program") for b in task.get("known_bad_programs") or []})
    programs.update({f"bot {b.get('name')!r}": b.get("program") for b in task.get("baseline_bots") or []})
    for label, prog in programs.items():
        for e in check(prog, palette, allowed, limits.get("max_blocks", 30), limits.get("max_depth", 5)):
            r.error(f"{label}: {e}")
    if r.errors:
        return r

    # Golden checks: the reference passes, each known-bad program fails the test it names.
    meta = _meta(task)
    ref = evaluate(meta, task["reference_program"], with_futures=False)
    if not ref["accepted"]:
        failed = [t["name"] for t in ref["obligatory"] if not t["passed"]]
        r.error(f"reference_program is not accepted (fails {failed})")
    elif ref["score"] < 80:
        r.warn(f"reference_program scores {ref['score']}; expected at least 80")
    for b in task.get("known_bad_programs") or []:
        res = evaluate(meta, b["program"], with_futures=False)
        failed = [t["name"] for t in res["obligatory"] if not t["passed"]]
        if res["accepted"]:
            r.error(f"known_bad {b['name']!r} is accepted (score {res['score']})")
        elif b.get("fails") and b["fails"] not in failed:
            r.error(f"known_bad {b['name']!r} should fail {b['fails']!r}, fails {failed}")
    return r


def _meta(task: dict) -> dict:
    return {"household": task["household"], "world": task["world"], "obligatory": task["obligatory"],
            "optional": task.get("optional") or [], "optional_metric": task.get("optional_metric"),
            "futures": task.get("futures") or {"n": 0, "seed": 0, "job_loss_per_month": 0, "job_loss_months": [1, 1],
                                                "shock_per_month": 0, "shock_amount": [0, 0]}}


# ---------------------------------------------------------------- compile and views

def compile_task(task: dict) -> dict:
    meta = _meta(task)
    meta["reference_growth"] = evaluate(meta, task["reference_program"])["futures"]["median_net_worth"]
    bots = [{"name": "Reference solution", "accepted": True, "score": None, "growth_index": 100, "reference": True}]
    for b in task.get("baseline_bots") or []:
        res = evaluate(meta, b["program"])
        bots.append({"name": b["name"], "accepted": res["accepted"], "score": res["score"],
                     "growth_index": res.get("growth_index")})
    bots[0]["score"] = evaluate(meta, task["reference_program"], with_futures=False)["score"]
    palette = [{"block": b, **BLOCKS[b]} for b in task["palette"]]
    return {
        "id": task["id"], "node": task["node"], "level": "hard", "content_version": task["content_version"],
        "live": bool(task.get("reviewer")),
        "question": {
            "brief": task["brief"],
            "palette": palette,
            "vars": [{"name": v, "label": VARS[v]} for v in task["vars"]],
            "limits": task.get("limits") or {},
            "starter_program": task.get("starter_program") or {"every_month": []},
            "household": task["household"],
            "months": task["world"]["months"],
            "assumptions": task.get("assumptions") or [],
            "obligatory": [t["name"] for t in task["obligatory"]],
            "optional_count": len(task.get("optional") or []),
            "bots": bots,
            "blockly": {"blocks": block_definitions(task["palette"], task["vars"]),
                        "toolbox": toolbox(task["palette"], task["vars"]),
                        "starter": program_to_workspace(task.get("starter_program") or {"every_month": []})},
        },
        "reveal": {
            "reference_program": task["reference_program"],
            "reference_workspace": program_to_workspace(task["reference_program"]),
            "editorial": task["editorial"],
            "optional": [{"name": t["name"], "probability": t["probability"]} for t in task.get("optional") or []],
            "sources": task.get("sources", []),
        },
        "meta": {**meta, "author": task.get("author"), "reviewer": task.get("reviewer"),
                 "content_file": task.get("_file")},
    }


def question_view(record: dict, lang: str = "en") -> dict:
    base = {k: record[k] for k in ("id", "node", "level", "content_version")}
    return {**base, **localize_all(record["question"], lang)}


def reveal_view(record: dict, lang: str = "en") -> dict:
    return localize_all(record["reveal"], lang)


def secrets(record: dict) -> dict:
    """For the tutor's leak check: the reference program's action blocks are not secret, but
    the optional events are. Kept small on purpose."""
    return {"strings": [t["name"] for t in record["reveal"]["optional"]], "numbers": []}


def score(record: dict, program: dict) -> dict:
    """POST /answers for a hard task. `program` is our program JSON or a Blockly workspace JSON
    (it has a "blocks" key). Field names match the attempt record (docs/task_engines.md)."""
    if isinstance(program, dict) and "blocks" in program:
        try:
            program = workspace_to_program(program)
        except ConversionError as e:
            raise AttemptError(str(e)) from e
    q = record["question"]
    errors = check(program, [b["block"] for b in q["palette"]], [v["name"] for v in q["vars"]],
                   q["limits"].get("max_blocks", 30), q["limits"].get("max_depth", 5))
    if errors:
        raise AttemptError("; ".join(errors))
    result = evaluate(record["meta"], copy.deepcopy(program))
    points = result.pop("score")  # 51-100 when accepted, None otherwise
    return {"task_id": record["id"], "content_version": record["content_version"], "level": "hard",
            "response": {"program": program}, "points": points,
            "score": None if points is None else points / 100, **result}
