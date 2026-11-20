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

from common import AttemptError, Report, check_source_ids, is_text, localize_all
from sim import Household, Scenario, metrics, run, synthetic_returns

from .dsl import BLOCKS, VARS, check, compile_program

CHECKS = {"no_card_debt", "contributed_at_least", "net_worth_at_least"}
OVERRIDES = {"job_loss", "shocks", "price_rise"}
PASS_SCORE, MAX_SCORE = 51, 100


# ---------------------------------------------------------------- simulation helpers

def _household(spec: dict) -> Household:
    return Household(**spec["household"])


def _returns(world: dict, seed_offset: int = 0) -> list[float]:
    m = world.get("market") or {}
    if m.get("kind", "synthetic") != "synthetic":
        raise ValueError(f"market kind {m.get('kind')!r} not implemented")
    return synthetic_returns(world["months"], m.get("seed", 1) + seed_offset, m.get("mean", 0.005), m.get("sd", 0.04))


def _scenario(world: dict, override: dict | None, returns: list[float]) -> Scenario:
    o = override or {}
    return Scenario(months=world["months"], returns=returns,
                    job_loss=[tuple(x) for x in o.get("job_loss", [])],
                    shocks={int(k): float(v) for k, v in (o.get("shocks") or {}).items()},
                    price_rise=tuple(o["price_rise"]) if o.get("price_rise") else None)


def _passes(check_spec: dict, m: dict) -> bool:
    ok = True
    if check_spec.get("no_card_debt"):
        ok &= m["card_debt_max"] == 0
    if "contributed_at_least" in check_spec:
        ok &= m["contributed"] >= check_spec["contributed_at_least"]
    if "net_worth_at_least" in check_spec:
        ok &= m["net_worth_end"] >= check_spec["net_worth_at_least"]
    return bool(ok)


def _optional_metric(m: dict) -> float:
    """1 = never needed the card; 0.5 = needed it but repaid it by the end; 0 = still in debt."""
    if m["card_debt_max"] == 0:
        return 1.0
    return 0.5 if m["card_debt_end"] == 0 else 0.0


def _futures(meta: dict, policy) -> dict:
    f, world = meta["futures"], meta["world"]
    rng = random.Random(f["seed"])
    clean = 0
    for i in range(f["n"]):
        job_loss, shocks = [], {}
        for month in range(1, world["months"] + 1):
            if not job_loss and rng.random() < f["job_loss_per_month"]:
                job_loss.append((month, rng.randint(*f["job_loss_months"])))
            if rng.random() < f["shock_per_month"]:
                shocks[month] = round(rng.uniform(*f["shock_amount"]), -1)
        sc = Scenario(world["months"], _returns(world, 1000 + i), job_loss, shocks)
        clean += metrics(run(_household(meta), policy, sc))["card_debt_max"] == 0
    return {"n": f["n"], "without_card_debt": clean}


def evaluate(meta: dict, program: dict, with_futures: bool = True) -> dict:
    """Run a checked program through every test. The core of score(); also used by the build."""
    policy = compile_program(program)
    base_returns = _returns(meta["world"])
    obligatory, story = [], None
    for t in meta["obligatory"]:
        rows = run(_household(meta), policy, _scenario(meta["world"], t.get("override"), base_returns))
        passed = _passes(t["check"], metrics(rows))
        obligatory.append({"name": t["name"], "passed": passed})
        if not passed and story is None:
            story = {"test": t["name"], "months": rows}
    accepted = all(t["passed"] for t in obligatory)
    optional, score = [], None
    if accepted:
        for t in meta["optional"]:
            rows = run(_household(meta), policy, _scenario(meta["world"], t.get("override"), base_returns))
            optional.append({"name": t["name"], "probability": t["probability"], "metric": _optional_metric(metrics(rows))})
        weight = sum(t["probability"] for t in optional)
        share = sum(t["probability"] * t["metric"] for t in optional) / weight if weight else 1.0
        score = round(PASS_SCORE + (MAX_SCORE - PASS_SCORE) * share)
    result = {"accepted": accepted, "score": score, "obligatory": obligatory, "optional": optional, "story": story}
    if accepted and with_futures:
        result["futures"] = _futures(meta, policy)
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
    if (world.get("market") or {}).get("kind", "synthetic") != "synthetic":
        r.error("world.market.kind: only synthetic is implemented")
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
            "optional": task.get("optional") or [],
            "futures": task.get("futures") or {"n": 0, "seed": 0, "job_loss_per_month": 0, "job_loss_months": [1, 1],
                                                "shock_per_month": 0, "shock_amount": [0, 0]}}


# ---------------------------------------------------------------- compile and views

def compile_task(task: dict) -> dict:
    meta = _meta(task)
    bots = []
    for b in task.get("baseline_bots") or []:
        res = evaluate(meta, b["program"], with_futures=False)
        bots.append({"name": b["name"], "accepted": res["accepted"], "score": res["score"]})
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
        },
        "reveal": {
            "reference_program": task["reference_program"],
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
    """POST /answers for a hard task. Field names match the attempt record (docs/task_engines.md)."""
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
