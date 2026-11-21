"""Admin and profile metrics on hand-made rows: each test states the number a person would compute."""
import datetime as dt
import re

import pytest

from analytics import (calibration_series, first_attempts, hard_overview, item_stats, participant_id, profile_summary,
                       report_alerts, study_report, tutor_overview)
from analytics.study import ALPHABET

T0 = dt.datetime(2026, 11, 21, 10, 0, tzinfo=dt.timezone.utc)


def att(user, task, score, p=None, minute=0, **kw):
    return {"id": minute, "user_id": user, "task_id": task, "node_id": kw.pop("node", "S1"), "level": kw.pop("level", "easy"),
            "context": kw.pop("context", "practice"), "response": kw.pop("response", 0), "score": score, "p": p,
            "submitted_at": T0 + dt.timedelta(minutes=minute), "started_at": T0 + dt.timedelta(minutes=minute) - dt.timedelta(seconds=30),
            "hints_used": kw.pop("hints_used", 0), "clarity_rating": kw.pop("clarity_rating", None), **kw}


def test_first_attempts_ignore_retries_after_the_reveal():
    rows = [att("u", "a", 1.0, minute=5), att("u", "a", 0.0, minute=1), att("v", "a", 1.0, minute=2)]
    assert [(a["user_id"], a["score"]) for a in first_attempts(rows)] == [("u", 0.0), ("v", 1.0)]


def test_item_stats_flags_overconfidence_and_strong_users_failing():
    rows = []
    for i in range(10):
        strong = i < 5
        rows.append(att(f"u{i}", "easy_ok", 1.0 if strong else 0.0, p=1.0, minute=i))         # half right, all sure
        rows.append(att(f"u{i}", "bad_key", 0.0 if strong else 1.0, p=0.5, minute=20 + i))    # strong users fail it
        rows.append(att(f"u{i}", "other", 1.0 if strong else 0.0, p=0.5, minute=40 + i))      # defines "strong"
    stats = {s["task_id"]: s for s in item_stats(rows, reports={"bad_key": 2})}
    assert stats["easy_ok"]["calibration_gap"] == 0.5 and "confidence_above_success" in stats["easy_ok"]["flags"]
    assert stats["bad_key"]["discrimination"] < 0 and {"strong_users_fail", "reported"} <= set(stats["bad_key"]["flags"])
    assert stats["easy_ok"]["median_time_s"] == 30 and stats["easy_ok"]["choices"] == {"0": 1.0}


def test_calibration_of_a_calibrated_user_is_zero():
    rows = [att("u", f"t{i}", s, p=s, minute=i) for i, s in enumerate([1.0, 0.0, 1.0, 0.5])]
    week = calibration_series(rows)["all"][0]
    assert week["gap"] == 0 and week["brier"] == 0 and week["n"] == 4


def test_hard_overview_by_hand():
    rows = [att("u", "s1.h1", None, level="hard", accepted=False, failed_test="Job loss", duration_ms=120, minute=1),
            att("u", "s1.h1", 0.97, level="hard", accepted=True, points=97, growth_index=100.0, duration_ms=150, minute=2),
            att("v", "s1.h1", 0.51, level="hard", accepted=True, points=51, growth_index=96.0, duration_ms=180, minute=3)]
    h = hard_overview(rows)[0]
    assert h["acceptance"] == pytest.approx(2 / 3, abs=1e-4) and h["first_attempt_acceptance"] == 0.5
    assert h["most_failed_test"] == "Job loss" and h["points_histogram"] == {"51-60": 1, "91-100": 1}
    assert h["median_growth_index"] == 98.0 and h["duration_ms_p50"] == 150


def test_tutor_advice_alert():
    ev = [{"ts": T0, "intent": "explain_concept", "checks_failed": [], "fallback_used": False, "latency_ms": 900}
          for _ in range(18)]
    ev += [{"ts": T0, "intent": "hint", "checks_failed": ["advice phrase: 'you should buy'"], "fallback_used": True,
            "flagged_for_review": True, "latency_ms": 1200} for _ in range(2)]
    o = tutor_overview(ev)
    assert o["advice_alert"]["share"] == 0.1 and o["advice_alert"]["on"] and o["checks_failed"] == {"advice phrase": 2}


def test_report_alerts_count_only_open_wrong_facts():
    fb = [{"target_id": "i2.e2", "kind": "wrong_fact", "status": "new"},
          {"target_id": "i2.e2", "kind": "wrong_fact", "status": "triaged"},
          {"target_id": "i2.e3", "kind": "wrong_fact", "status": "fixed"},
          {"target_id": "i2.e3", "kind": "unclear", "status": "new"}]
    assert report_alerts(fb) == [{"target_id": "i2.e2", "open_wrong_fact_reports": 2, "level": "red"}]


def test_study_report_paired_changes():
    pairs = [{"participant_id": "FQ-AAAA", "before": {"confidence": 2, "score": 2}, "after": {"confidence": 4, "score": 3}},
             {"participant_id": "FQ-BBBB", "before": {"confidence": 3, "score": 4}, "after": {"confidence": 3, "score": 3}}]
    r = study_report(pairs)
    assert r["metrics"]["confidence"] == {"n": 2, "mean_before": 2.5, "mean_after": 3.5, "mean_change": 1.0,
                                          "up": 1, "same": 1, "down": 0}
    assert r["metrics"]["score"]["down"] == 1 and "not a controlled trial" in r["note"]


def test_participant_ids_are_readable_and_unique():
    existing = set()
    for _ in range(200):
        code = participant_id(existing)
        assert re.fullmatch(r"FQ-[" + ALPHABET + "]{4}", code) and code not in existing
        existing.add(code)
    assert not set("01OI") & set(ALPHABET)


def test_profile_mastery_moves_with_first_attempts_and_badge_needs_20():
    tree = {"S1": {"title": "Emergency fund", "panel": "SAFETY"}, "I1": {"title": "Risk", "panel": "INSTRUMENTS"}}
    rows = [att("u", f"s1.e{i}", 1.0, p=1.0, node="S1", minute=i) for i in range(3)]
    p = profile_summary(rows, tree, router_result={"mastery": {"S1": 0.5, "I1": 0.5}}, now=T0)
    s1 = next(n for panel in p["panels"] for n in panel["nodes"] if n["node"] == "S1")
    assert s1["mastery"] > 0.5 and p["calibration"]["gap"] == 0.0 and not p["calibration"]["well_calibrated_badge"]
    rows20 = [att("u", f"t{i}", 1.0, p=1.0, node="I1", minute=i) for i in range(20)]
    assert profile_summary(rows20, tree, now=T0)["calibration"]["well_calibrated_badge"]
