import copy
import json

import pytest

from common import AttemptError, load_sources
from hard.build import build, load_tasks
from hard.dsl import check, compile_program
from hard.task import question_view, score, validate
from sim import Household, Scenario, metrics, run


# ---------------------------------------------------------------- simulation core

def test_ledger_order_by_hand():
    # Every hard score depends on the month order: costs, then the policy, then buffer before card.
    h = Household(income=1000, costs=800, buffer=100, buffer_rate=0, card_rate=0)
    sc = Scenario(months=3, returns=[0, 0, 0], job_loss=[(2, 1)])
    rows = run(h, lambda ctx: [("invest", 10_000)], sc)  # asks for more than there is: capped
    assert [r["invested"] for r in rows] == [200, 200, 400]
    assert (rows[1]["from_buffer"], rows[1]["from_card"]) == (100, 700)
    assert rows[2]["card_debt"] == 700 and metrics(rows)["card_debt_max"] == 700


def test_rates_apply_monthly():
    h = Household(income=0, costs=1, buffer=1200, buffer_rate=0.12, card_rate=0)
    rows = run(h, lambda ctx: [], Scenario(months=1, returns=[0.1], shocks={}))
    assert rows[0]["buffer"] == pytest.approx((1200 - 1) * 1.01, abs=0.01)


# ---------------------------------------------------------------- block language

PALETTE = ["if_else", "compare", "number", "invest", "save_to_buffer"]


@pytest.mark.parametrize("program, message", [
    ({"every_month": [{"block": "pay_debt", "amount": {"block": "number", "value": 1}}]}, "not available"),
    ({"every_month": [{"block": "if_else", "if": {"block": "number", "value": 1}, "then": [], "else": []}]}, "not a condition"),
    ({"every_month": [{"block": "invest", "amount": {"block": "var", "name": "secret"}}]}, "not available"),
    ({"every_month": [{"block": "invest", "amount": {"block": "compare", "op": "<",
                                                       "left": {"block": "number", "value": 1},
                                                       "right": {"block": "number", "value": 2}}}]}, "not a number"),
    ({"every_month": "invest"}, "must be"),
])
def test_bad_programs_are_rejected(program, message):
    # User programs are untrusted input; anything malformed must be refused before it runs.
    errors = check(program, PALETTE, ["cash"], max_blocks=10, max_depth=3)
    assert errors and any(message in e for e in errors), errors


def test_compiled_program_follows_the_branches():
    prog = {"every_month": [{"block": "if_else",
                             "if": {"block": "compare", "op": "<", "left": {"block": "var", "name": "cash"},
                                    "right": {"block": "number", "value": 100}},
                             "then": [{"block": "save_to_buffer", "amount": {"block": "var", "name": "cash"}}],
                             "else": [{"block": "invest", "amount": {"block": "number", "value": 100}}]}]}
    assert check(prog, PALETTE, ["cash"], 10, 3) == []
    policy = compile_program(prog)
    assert policy({"cash": 50}) == [("save_to_buffer", 50.0)]
    assert policy({"cash": 500}) == [("invest", 100.0)]


# ---------------------------------------------------------------- content and scoring

@pytest.fixture(scope="module")
def s1():
    results = {tid: (rec, r) for tid, rec, r, _ in build()}
    rec, r = results["s1.h1"]
    assert rec, r.errors  # golden checks: reference accepted, known-bad programs fail the named test
    return rec


def test_reference_scores_and_bots_are_ordered(s1):
    # The score must separate rules by resilience: a 2-month buffer scores below the reference.
    task = [t for t in load_tasks() if t["id"] == "s1.h1"][0]
    ref = score(s1, task["reference_program"])
    two_months = [b for b in s1["question"]["bots"] if b["name"].startswith("Buffer of 2")][0]
    assert ref["accepted"] and 51 <= two_months["score"] < ref["points"] <= 100


def test_second_axis_shows_the_trade_off(s1):
    # The 2-D score exists to show that a bigger buffer buys resilience at the cost of growth.
    bots = {b["name"]: b for b in s1["question"]["bots"]}
    six = bots["Buffer of 6 months, then invests"]
    ref = bots["Reference solution"]
    assert six["score"] > ref["score"] and six["growth_index"] < ref["growth_index"] == 100


def test_rejected_program_gets_the_failing_story(s1):
    res = score(s1, {"every_month": [{"block": "invest", "amount": {"block": "var", "name": "cash"}}]})
    assert not res["accepted"] and res["points"] is None
    assert res["story"]["test"].startswith("Job loss in month 6") and any(m["from_card"] > 0 for m in res["story"]["months"])


def test_scoring_is_deterministic(s1):
    task = [t for t in load_tasks() if t["id"] == "s1.h1"][0]
    assert score(s1, task["reference_program"]) == score(s1, task["reference_program"])


def test_question_view_hides_the_solution_and_the_surprises(s1):
    dumped = json.dumps(question_view(s1))
    assert "reference_program" not in dumped and "editorial" not in dumped and "meta" not in dumped
    assert all(o["name"] not in dumped for o in s1["reveal"]["optional"])


def test_invalid_program_raises(s1):
    with pytest.raises(AttemptError):
        score(s1, {"every_month": [{"block": "nope"}]})


def test_a_known_bad_program_that_passes_is_a_content_error():
    task = copy.deepcopy([t for t in load_tasks() if t["id"] == "s1.h1"][0])
    task["known_bad_programs"].append({"name": "Actually good", "program": task["reference_program"]})
    r = validate(task, load_sources())
    assert any("is accepted" in e for e in r.errors)
