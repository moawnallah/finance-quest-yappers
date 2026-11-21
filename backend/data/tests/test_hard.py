import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from common import AttemptError, load_sources
from hard.build import build, load_tasks
from hard.dsl import check, compile_program
from hard.task import _meta, compile_task, evaluate, question_view, score, validate
from sim import Household, Scenario, metrics, run

BASELINE = Path(__file__).resolve().parent / "fixtures" / "hard_baseline"


def frozen(task_id: str) -> dict:
    """A hard task as it was built on 2026-11-21, before the harder-situations work."""
    return yaml.safe_load((BASELINE / f"{task_id.replace('.', '_')}.yaml").read_text(encoding="utf-8"))


def compiled(task: dict) -> dict:
    r = validate(task, load_sources())
    assert not r.errors, r.errors  # golden checks: reference accepted, known-bad programs fail the named test
    return compile_task(task)


def content_task(task_id: str) -> dict:
    return [t for t in load_tasks() if t["id"] == task_id][0]


@pytest.fixture(scope="module")
def built():
    results = {tid: (rec, r) for tid, rec, r, _ in build()}
    for tid, (rec, r) in results.items():
        assert rec, (tid, r.errors)
    return {tid: rec for tid, (rec, _) in results.items()}


# ---------------------------------------------------------------- regression baseline

def _summary(r: dict) -> dict:
    return {"accepted": r["accepted"], "score": r["score"], "futures": r.get("futures"),
            "story_test": (r.get("story") or {}).get("test"),
            "sha256_full": hashlib.sha256(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()}


@pytest.mark.parametrize("task_id", ["s1.h1", "p4.h1"])
def test_new_mechanisms_leave_the_frozen_tasks_identical(task_id):
    # Every new mechanism is off by default (docs/hard_engine.md, "Next version"); if a task that does not
    # use them changes by one byte, the engine change broke something.
    task = frozen(task_id)
    expected = json.loads((BASELINE / "expected.json").read_text(encoding="utf-8"))[task_id]
    programs = {"reference": task["reference_program"],
                **{f"bot: {b['name']}": b["program"] for b in task.get("baseline_bots", [])},
                **{f"known_bad: {b['name']}": b["program"] for b in task.get("known_bad_programs", [])}}
    for name, program in programs.items():
        assert _summary(evaluate(_meta(task), program)) == expected[name], name


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


def test_tax_on_realised_gains_by_hand():
    # P4 v2's lesson rests on this: selling at a gain costs 19% of the gain at year end, measured on the average price.
    h = Household(income=0, costs=0.0001, buffer=1000, invested={"shares": 1000}, target={"shares": 1.0},
                  tax_on_gains=0.19, buffer_rate=0, card_rate=0)
    returns = [1.0] + [0.0] * 11                           # the fund doubles in month 1: 1000 -> 2000
    plan = {2: [("sell", 1000, "shares")]}                 # half is sold: cost basis 500, gain 500
    rows = run(h, lambda ctx: plan.get(ctx["month"], []), Scenario(months=12, returns={"shares": returns}))
    assert rows[11]["tax"] == pytest.approx(95.0) and rows[11]["from_buffer"] == pytest.approx(95.0, abs=0.01)
    assert all(r["tax"] == 0 for r in rows[:11])


def test_fees_by_hand():
    # The minimum fee is what makes small, frequent trades costly; the bond's early-sale fee is what makes it a poor buffer.
    h = Household(income=1000, costs=0.0001, invested={"fund": 0, "bond": 1000}, broker_fee={"rate": 0.0029, "min": 5},
                  sell_fee={"bond": 0.01}, buffer_rate=0, card_rate=0)
    plan = [("invest_in", 100, "fund"), ("sell", 100, "bond"), ("save_to_buffer", 10_000)]
    row = run(h, lambda ctx: plan, Scenario(months=1, returns={"fund": [0], "bond": [0]}))[0]
    assert row["holdings"] == {"fund": 95.0, "bond": 900.0}               # 100 - 5 PLN minimum fee
    assert row["buffer"] == pytest.approx(1000 - 100 + (100 - 5 - 1), abs=0.01)   # sale: -5 fee, -1 early-sale fee


def test_bills_are_paid_from_the_pot_first():
    # The capstone's bills pot only teaches something if a bill really drains the month's money when the pot is short.
    h = Household(income=2000, costs=1000, pot=1000, bills=[{"name": "Insurance", "amount": 1800, "month": 2, "every": 12}],
                  buffer_rate=0, card_rate=0)
    seen = []
    rows = run(h, lambda ctx: seen.append((ctx["next_bill"], ctx["months_to_next_bill"], ctx["cash"])) or [],
               Scenario(months=2, returns=[0, 0]))
    assert seen[0][:2] == (1800, 1) and seen[1][2] == 2000 - 1000 - 800   # month 2: the pot pays 1000 of the 1800
    assert rows[1]["pot"] == 0 and rows[1]["bill"] == 1800


def test_card_minimum_and_moving_target():
    h = Household(income=1000, costs=0.0001, card_debt=1000, card_min_payment=0.03, card_rate=0, buffer_rate=0,
                  invested={"shares": 600, "bonds": 400}, target={"shares": 0.6, "bonds": 0.4},
                  glide={"asset": "shares", "from": 0.6, "to": 0.4})
    rows = run(h, lambda ctx: [], Scenario(months=3, returns={"shares": [0] * 3, "bonds": [0] * 3}))
    assert rows[0]["card_debt"] == pytest.approx(970) and rows[0]["from_card"] == 0
    assert [r["target"] for r in rows] == [0.6, 0.5, 0.4]


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


OWN = ["if", "compare", "number", "invest", "set_var", "change_var", "my_var"]


def test_own_variables_keep_their_value_across_months_and_restart_each_run():
    # A variable is only useful as memory ("months since..."); a value leaking into the next scenario would mix tests.
    prog = {"every_month": [
        {"block": "change_var", "name": "months_seen", "value": {"block": "number", "value": 1}},
        {"block": "if", "if": {"block": "compare", "op": ">", "left": {"block": "my_var", "name": "months_seen"},
                               "right": {"block": "number", "value": 2}},
         "then": [{"block": "invest", "amount": {"block": "var", "name": "cash"}}]}]}
    assert check(prog, OWN, ["cash"], 10, 3) == []
    policy = compile_program(prog)
    h = Household(income=100, costs=0.0001, buffer_rate=0, card_rate=0)
    first = run(h, policy, Scenario(months=4, returns=[0] * 4))
    assert [r["contributed"] > 0 for r in first] == [False, False, True, True]
    assert run(h, policy, Scenario(months=4, returns=[0] * 4)) == first


@pytest.mark.parametrize("names, message", [
    (["a", "b", "c", "d"], "limit is 3"),
    (["cash"], "built-in value"),
    (["2fast"], "letters, digits"),
])
def test_own_variable_rules(names, message):
    prog = {"every_month": [{"block": "set_var", "name": n, "value": {"block": "number", "value": 1}} for n in names]}
    errors = check(prog, OWN, ["cash"], 20, 3)
    assert any(message in e for e in errors), errors


def test_dividing_by_zero_gives_zero():
    prog = {"every_month": [{"block": "invest", "amount": {"block": "math", "op": "/", "left": {"block": "number", "value": 5},
                                                             "right": {"block": "number", "value": 0}}}]}
    assert compile_program(prog)({}) == [("invest", 0.0)]


def test_asset_blocks_need_an_asset_of_the_task():
    prog = {"every_month": [{"block": "invest_in", "amount": {"block": "number", "value": 1}, "asset": "gold"}]}
    assert any("asset 'gold'" in e for e in check(prog, ["invest_in", "number"], [], 10, 3, assets=["fund"]))


# ---------------------------------------------------------------- frozen s1.h1: engine behaviour on a simple task

@pytest.fixture(scope="module")
def s1():
    return compiled(frozen("s1.h1"))


def test_reference_scores_and_bots_are_ordered(s1):
    # The score must separate rules by resilience: a 2-month buffer scores below the reference.
    ref = score(s1, frozen("s1.h1")["reference_program"])
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
    program = frozen("s1.h1")["reference_program"]
    assert score(s1, program) == score(s1, program)


def test_question_view_hides_the_solution_and_the_surprises(built):
    for rec in built.values():
        dumped = json.dumps(question_view(rec))
        assert "reference_program" not in dumped and "editorial" not in dumped and "meta" not in dumped
        assert all(o["name"] not in dumped for o in rec["reveal"]["optional"])


def test_invalid_program_raises(s1):
    with pytest.raises(AttemptError):
        score(s1, {"every_month": [{"block": "nope"}]})


def test_a_known_bad_program_that_passes_is_a_content_error():
    task = copy.deepcopy(frozen("s1.h1"))
    task["known_bad_programs"].append({"name": "Actually good", "program": task["reference_program"]})
    r = validate(task, load_sources())
    assert any("is accepted" in e for e in r.errors)


# ---------------------------------------------------------------- multi-asset household (frozen p4.h1 v1)

def test_multi_asset_ledger_by_hand():
    # P4 depends on these three moves: buy in the target mix, rebalance with a fee, sell pro rata.
    h = Household(income=1000, costs=0.0001, buffer=0, invested={"shares": 700, "bonds": 300},
                  target={"shares": 0.6, "bonds": 0.4}, trade_fee=0.01, buffer_rate=0, card_rate=0)
    sc = Scenario(months=2, returns={"shares": [0, 0], "bonds": [0, 0]})
    plan = [[("rebalance", 0), ("invest", 1000)], [("sell_investments", 400)]]
    rows = run(h, lambda ctx: plan[ctx["month"] - 1], sc)
    # month 1: rebalance 700/300 -> 600/400 moves 100, fee 2 x 100 x 1% = 2 (split 60/40); invest 1000 at 60/40
    assert rows[0]["holdings"] == pytest.approx({"shares": 600 - 1.2 + 600, "bonds": 400 - 0.8 + 400}, abs=0.01)
    # month 2: sell 400 pro rata, keeping the 60/40 mix
    assert rows[1]["weights"]["shares"] == pytest.approx(0.6, abs=1e-3)
    assert rows[1]["invested"] == pytest.approx(1998 - 400, abs=0.01)


@pytest.fixture(scope="module")
def p4_v1():
    return compiled(frozen("p4.h1"))


def test_p4_panic_seller_fails_the_crash_test(p4_v1):
    panic = frozen("p4.h1")["known_bad_programs"][1]["program"]
    res = score(p4_v1, panic)
    failed = [t["name"] for t in res["obligatory"] if not t["passed"]]
    assert not res["accepted"] and any(name.startswith("A crash") for name in failed)


def test_p4_waiting_for_10_points_leaves_the_band(p4_v1):
    # The rally test is what separates "act at 5 points" from "act at 10 points".
    bots = {b["name"]: b for b in p4_v1["question"]["bots"]}
    assert not bots["Rebalances when 10 points off"]["accepted"] and bots["Reference solution"]["score"] == 100


# ---------------------------------------------------------------- harder situations: the lessons the content must keep

def test_p4_v2_rebalancing_too_often_or_ignoring_new_money_costs_growth(built):
    # P4 v2 exists to teach that fees and tax punish needless trading; if these bots stop losing growth, the lesson is gone.
    bots = {b["name"]: b for b in built["p4.h1"]["question"]["bots"]}
    assert bots["Rebalances every month"]["growth_index"] < 100
    assert bots["New money always into shares, rebalance at 5 points"]["growth_index"] < 100
    assert not bots["Never rebalances"]["accepted"]


def test_capstone_rewards_the_pot_and_punishes_one_company(built):
    # The capstone combines S1 (buffer, bills pot) with I4 and P1 (one company vs a fund): each bot must lose on its own axis.
    bots = {b["name"]: b for b in built["p1.h1"]["question"]["bots"]}
    ref = bots["Reference solution"]
    no_pot = next(b for n, b in bots.items() if n.startswith("Buffer of 3 months"))
    assert no_pot["score"] < ref["score"]
    assert bots["Like the reference, but everything in CrocoTech"]["growth_index"] < 100


def test_capstone_job_loss_comes_at_unknown_times():
    # A rule fitted to one job-loss month must fail: the test runs four timings and all must pass.
    task = content_task("p1.h1")
    lazy = next(b for b in task["known_bad_programs"] if b["name"].startswith("Save 1,000"))["program"]
    meta = _meta(task)
    res = evaluate(meta, lazy, with_futures=False)
    assert not res["accepted"] and res["story"]["test"].startswith("A 2-month job loss")
    late_only = copy.deepcopy(meta)
    late_only["obligatory"][0]["variants"] = [{"job_loss": [[10, 2]]}]
    assert evaluate(late_only, lazy, with_futures=False)["obligatory"][0]["passed"]   # one timing alone lets it through
