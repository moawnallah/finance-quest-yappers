"""Metrics for the admin views and the profile (docs/admin_and_profile.md).

Rows are dicts with the database's field names. Attempts: id, user_id, task_id, node_id, level,
context, response, confidence, p, score, accepted, started_at, submitted_at, hints_used,
clarity_rating, points, growth_index, duration_ms, failed_test. Datetimes may be datetime objects
or ISO strings.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import statistics
from collections import Counter, defaultdict

FREE_HINTS = 2
K_MASTERY = 0.4
BANDS = ((0.8, "mastered"), (0.6, "solid"), (0.0, "learning"))


# ---------------------------------------------------------------- helpers

def _ts(v) -> dt.datetime | None:
    """A timezone-aware datetime. SQLite returns naive datetimes; they are stored in UTC."""
    if v is None:
        return None
    t = v if isinstance(v, dt.datetime) else dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.fmean(xs), 4) if xs else None


def _pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    i = min(len(xs) - 1, max(0, math.ceil(q / 100 * len(xs)) - 1))
    return xs[i]


def _corr(xs, ys):
    if len(xs) < 5:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy), 4)


def _order(a: dict):
    return (_ts(a.get("submitted_at")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc), a.get("id", 0))


def first_attempts(attempts: list[dict]) -> list[dict]:
    """The first attempt per user and task. Content quality and completion use only these, because
    the reveal shows the answer and later attempts are practice."""
    seen, out = set(), []
    for a in sorted(attempts, key=_order):
        key = (a["user_id"], a["task_id"])
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


# ---------------------------------------------------------------- view B: questions and tasks

def _choice_keys(a: dict) -> list[str]:
    r = a.get("response")
    if a.get("level") == "medium" and isinstance(r, dict):
        return [f"value:{r.get('value')}"] + [f"reason:{x}" for x in r.get("reasons") or []]
    return [json.dumps(r, sort_keys=True)]


def item_stats(attempts: list[dict], reports: dict[str, int] | None = None, min_n: int = 10) -> list[dict]:
    """Per item or task, from first attempts: n, success, confidence, calibration gap, discrimination
    (correlation of the item score with the user's mean on their other first attempts), choice shares,
    time, clarity, hints, reports, and flags."""
    reports = reports or {}
    first = [a for a in first_attempts(attempts) if a.get("score") is not None]
    by_user = defaultdict(list)
    for a in first:
        by_user[a["user_id"]].append(a)
    by_task = defaultdict(list)
    for a in first:
        by_task[a["task_id"]].append(a)

    out = []
    for task_id, rows in by_task.items():
        scores = [a["score"] for a in rows]
        with_p = [a for a in rows if a.get("p") is not None]
        success = _mean(scores)
        mean_p = _mean([a["p"] for a in with_p])
        gap = round(mean_p - _mean([a["score"] for a in with_p]), 4) if with_p else None
        pairs = []
        for a in rows:
            others = [b["score"] for b in by_user[a["user_id"]] if b["task_id"] != task_id]
            if others:
                pairs.append((a["score"], statistics.fmean(others)))
        disc = _corr([x for x, _ in pairs], [y for _, y in pairs]) if pairs else None
        choices = Counter(k for a in rows for k in _choice_keys(a))
        times = [(_ts(a["submitted_at"]) - _ts(a["started_at"])).total_seconds()
                 for a in rows if a.get("started_at") and a.get("submitted_at")]
        n = len(rows)
        flags = []
        if n >= min_n and gap is not None and gap > 0.2:
            flags.append("confidence_above_success")
        if n >= min_n and disc is not None and disc < 0:
            flags.append("strong_users_fail")
        if n >= min_n and success is not None and success > 0.95:
            flags.append("too_easy")
        if n >= min_n and success is not None and success < 0.2:
            flags.append("too_hard")
        if reports.get(task_id, 0) >= 2:
            flags.append("reported")
        out.append({"task_id": task_id, "node": rows[0].get("node_id"), "level": rows[0].get("level"), "n": n,
                    "success": success, "mean_confidence": mean_p, "calibration_gap": gap, "discrimination": disc,
                    "choices": {k: round(v / n, 4) for k, v in choices.most_common()},
                    "median_time_s": statistics.median(times) if times else None,
                    "clarity": _mean([a.get("clarity_rating") for a in rows]),
                    "hint_share": round(sum(1 for a in rows if (a.get("hints_used") or 0) > 0) / n, 4),
                    "paid_hint_share": round(sum(1 for a in rows if (a.get("hints_used") or 0) > FREE_HINTS) / n, 4),
                    "reports": reports.get(task_id, 0), "flags": flags})
    return sorted(out, key=lambda r: (-len(r["flags"]), r["task_id"]))


def hard_overview(attempts: list[dict]) -> list[dict]:
    """Per hard task: attempts, users, acceptance (all and first attempts), the most failed obligatory
    test, the points histogram, median growth, and engine time."""
    by_task = defaultdict(list)
    for a in attempts:
        if a.get("level") == "hard":
            by_task[a["task_id"]].append(a)
    out = []
    for task_id, rows in sorted(by_task.items()):
        firsts = first_attempts(rows)
        accepted = [a for a in rows if a.get("accepted")]
        bins = Counter()
        for a in accepted:
            p = a.get("points")
            if p is not None:
                bins[f"{max(51, (p - 1) // 10 * 10 + 1)}-{min(100, (p - 1) // 10 * 10 + 10)}"] += 1
        failed = Counter(a.get("failed_test") for a in rows if not a.get("accepted") and a.get("failed_test"))
        out.append({"task_id": task_id, "attempts": len(rows), "users": len({a["user_id"] for a in rows}),
                    "acceptance": round(len(accepted) / len(rows), 4),
                    "first_attempt_acceptance": _mean([1.0 if a.get("accepted") else 0.0 for a in firsts]),
                    "most_failed_test": failed.most_common(1)[0][0] if failed else None,
                    "points_histogram": dict(sorted(bins.items())),
                    "median_growth_index": statistics.median([a["growth_index"] for a in accepted
                                                              if a.get("growth_index") is not None]) if accepted else None,
                    "duration_ms_p50": _pct([a.get("duration_ms") for a in rows], 50),
                    "duration_ms_p95": _pct([a.get("duration_ms") for a in rows], 95)})
    return out


# ---------------------------------------------------------------- view C: self-assessment trend

def _week(ts: dt.datetime) -> str:
    y, w, _ = ts.isocalendar()
    return f"{y}-W{w:02d}"


def _calib(rows: list[dict]) -> dict:
    ps, ss = [a["p"] for a in rows], [a["score"] for a in rows]
    return {"n": len(rows), "mean_confidence": _mean(ps), "mean_score": _mean(ss),
            "gap": round(statistics.fmean(ps) - statistics.fmean(ss), 4) if rows else None,
            "brier": round(statistics.fmean((p - s) ** 2 for p, s in zip(ps, ss)), 4) if rows else None}


def calibration_series(attempts: list[dict], groups: dict[str, str] | None = None) -> dict:
    """Weekly confidence vs score from first attempts with both. groups: user_id -> label (e.g. age band)."""
    rows = [a for a in first_attempts(attempts) if a.get("p") is not None and a.get("score") is not None]

    def series(rs):
        weeks = defaultdict(list)
        for a in rs:
            weeks[_week(_ts(a["submitted_at"]))].append(a)
        return [{"week": w, **_calib(weeks[w])} for w in sorted(weeks)]

    out = {"all": series(rows), "groups": {}}
    if groups:
        by = defaultdict(list)
        for a in rows:
            by[groups.get(a["user_id"], "unknown")].append(a)
        out["groups"] = {g: series(rs) for g, rs in sorted(by.items())}
    return out


# ---------------------------------------------------------------- view D: AI overview

def tutor_overview(events: list[dict], now: dt.datetime | None = None, alert_share: float = 0.05) -> dict:
    """llm_events: intents, check failures by type, fallbacks, flagged, latency, models; and the alert
    "advice or leak check failures above 5% of answers in the last hour"."""
    n = len(events)
    checks = Counter(c.split(":")[0] for e in events for c in (e.get("checks_failed") or []))
    lat = [e.get("latency_ms") for e in events]
    now = now or max((_ts(e["ts"]) for e in events), default=None)
    recent = [e for e in events if now and _ts(e["ts"]) >= now - dt.timedelta(hours=1)]
    bad = [e for e in recent if any(c.split(":")[0].startswith(("advice", "leaks", "ISIN", "ticker", "named product"))
                                    for c in (e.get("checks_failed") or []))]
    share = round(len(bad) / len(recent), 4) if recent else 0.0
    return {"n": n, "intents": dict(Counter(e.get("intent") for e in events)), "checks_failed": dict(checks),
            "fallback_rate": round(sum(1 for e in events if e.get("fallback_used")) / n, 4) if n else None,
            "flagged": sum(1 for e in events if e.get("flagged_for_review")),
            "latency_ms_p50": _pct(lat, 50), "latency_ms_p95": _pct(lat, 95),
            "models": dict(Counter(e.get("model") for e in events)),
            "advice_alert": {"last_hour": len(recent), "failing": len(bad), "share": share, "on": share > alert_share}}


# ---------------------------------------------------------------- view G: reports

def report_alerts(feedback: list[dict], threshold: int = 2) -> list[dict]:
    """Red alerts: a target with `threshold` or more open "wrong fact" reports. The item stays live."""
    open_counts = Counter(f["target_id"] for f in feedback
                          if f.get("kind") == "wrong_fact" and f.get("status", "new") in ("new", "triaged"))
    return [{"target_id": t, "open_wrong_fact_reports": c, "level": "red"}
            for t, c in sorted(open_counts.items()) if c >= threshold]


# ---------------------------------------------------------------- view H: study

def study_report(pairs: list[dict]) -> dict:
    """pairs: [{participant_id, before: {metric: value}, after: {metric: value}}]. Paired changes."""
    metrics = sorted({m for p in pairs for m in (p.get("before") or {})} & {m for p in pairs for m in (p.get("after") or {})})
    out = {"participants": len(pairs), "note": f"Hallway test, n = {len(pairs)}, not a controlled trial.", "metrics": {}}
    for m in metrics:
        both = [(p["before"][m], p["after"][m]) for p in pairs
                if p["before"].get(m) is not None and p["after"].get(m) is not None]
        diffs = [a - b for b, a in both]
        out["metrics"][m] = {"n": len(both), "mean_before": _mean([b for b, _ in both]),
                             "mean_after": _mean([a for _, a in both]), "mean_change": _mean(diffs),
                             "up": sum(d > 0 for d in diffs), "same": sum(d == 0 for d in diffs),
                             "down": sum(d < 0 for d in diffs)}
    return out


# ---------------------------------------------------------------- profile

def _band(m: float) -> str:
    return next(label for limit, label in BANDS if m >= limit)


def profile_summary(attempts: list[dict], tree: dict[str, dict], node_states: dict[str, dict] | None = None,
                    router_result: dict | None = None, now: dt.datetime | None = None) -> dict:
    """One user's profile (docs/admin_and_profile.md, "User profile"). attempts: this user's rows.
    node_states: the API's completion per node (done, easy_done, ...). Mastery starts from the
    router and moves with each first practice attempt: theta += K * (score - m), on the logit scale."""
    node_states = node_states or {}
    start = (router_result or {}).get("mastery") or {}
    theta = {k: math.log(max(1e-6, start.get(k, 0.5)) / max(1e-6, 1 - start.get(k, 0.5))) for k in tree}
    for a in first_attempts(attempts):
        k = a.get("node_id")
        if k in theta and a.get("score") is not None and a.get("context") == "practice":
            m = 1 / (1 + math.exp(-theta[k]))
            theta[k] += K_MASTERY * (a["score"] - m)
    mastery = {k: round(1 / (1 + math.exp(-t)), 3) for k, t in theta.items()}

    panels = defaultdict(list)
    for k, n in tree.items():
        st = node_states.get(k) or {}
        panels[n["panel"]].append({"node": k, "title": n["title"], "mastery": mastery[k], "band": _band(mastery[k]),
                                   "done": bool(st.get("done")), "challenge_passed": bool((st.get("test_out") or {}).get("passed"))})

    scored = [a for a in sorted(attempts, key=_order) if a.get("p") is not None and a.get("score") is not None][-20:]
    gap = round(statistics.fmean(a["p"] for a in scored) - statistics.fmean(a["score"] for a in scored), 4) if scored else None
    words = None if gap is None else "about right" if abs(gap) < 0.1 else \
        "more sure than right" if gap > 0 else "less sure than right"

    hard = defaultdict(lambda: {"attempts": 0, "accepted": False, "best_points": None, "best_growth_index": None})
    for a in attempts:
        if a.get("level") == "hard":
            h = hard[a["task_id"]]
            h["attempts"] += 1
            if a.get("accepted"):
                h["accepted"] = True
                h["best_points"] = max(h["best_points"] or 0, a.get("points") or 0)
                if a.get("growth_index") is not None:
                    h["best_growth_index"] = max(h["best_growth_index"] or 0, a["growth_index"])

    now = now or dt.datetime.now(dt.timezone.utc)
    recent = [a for a in attempts if _ts(a["submitted_at"]) >= now - dt.timedelta(days=7)]
    r = router_result or {}
    return {
        "path": r.get("path", []), "goal": r.get("goal"), "challenges": r.get("challenges", []),
        "benchmarks": r.get("benchmarks"),
        "panels": [{"panel": p, "nodes": nodes, "done": sum(n["done"] for n in nodes), "total": len(nodes)}
                   for p, nodes in panels.items()],
        "calibration": {"last_n": len(scored), "gap": gap, "in_words": words,
                        "brier": round(statistics.fmean((a["p"] - a["score"]) ** 2 for a in scored), 4) if scored else None,
                        "well_calibrated_badge": len(scored) >= 20 and gap is not None and abs(gap) < 0.1,
                        "weekly": calibration_series(attempts)["all"]},
        "hard": dict(hard),
        "activity": {"attempts_last_7_days": len(recent),
                     "active_days_last_7": len({_ts(a["submitted_at"]).date() for a in recent})},
    }
