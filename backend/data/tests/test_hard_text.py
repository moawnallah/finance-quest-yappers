"""The text form of hard-task programs (data/hard/text.py)."""
import pytest

from hard import load_records
from hard.dsl import check
from hard.task import evaluate, public_tests, run_public
from hard.text import TextError, to_program, to_text

RECORDS = load_records()


@pytest.mark.parametrize("tid", sorted(RECORDS))
def test_reference_round_trips_and_scores_the_same(tid):
    rec = RECORDS[tid]
    ref = rec["reveal"]["reference_program"]
    q = rec["question"]
    code = to_text(ref)
    back = to_program(code, [v["name"] for v in q["vars"]], [a["name"] for a in q.get("assets") or []])
    assert check(back, [b["block"] for b in q["palette"]], [v["name"] for v in q["vars"]],
                 q["limits"].get("max_blocks", 30), q["limits"].get("max_depth", 5),
                 [a["name"] for a in q.get("assets") or []]) == []
    assert evaluate(rec["meta"], back, with_futures=False)["score"] == evaluate(rec["meta"], ref, with_futures=False)["score"]
    assert to_text(back) == code


def test_parses_the_documented_forms():
    code = """
# every month
if buffer_months < 2 and not (card_debt > 0):
    save_to_buffer(cash)
elif cash > 12_000:
    invest_in(cash * 0.5, shares)
    saved += 1
else:
    save_to_pot(min(next_bill - pot, cash))
    saved = -1
rebalance()
"""
    p = to_program(code, ["buffer_months", "card_debt", "cash", "next_bill", "pot"], ["shares"])
    first = p["every_month"][0]
    assert first["block"] == "if_else" and first["if"]["block"] == "and"
    assert first["else"][0]["then"][0] == {"block": "invest_in", "asset": "shares",
                                            "amount": {"block": "math", "op": "*", "left": {"block": "var", "name": "cash"},
                                                       "right": {"block": "number", "value": 0.5}}}
    assert first["else"][0]["then"][1] == {"block": "change_var", "name": "saved", "value": {"block": "number", "value": 1}}
    assert p["every_month"][1] == {"block": "rebalance"}


@pytest.mark.parametrize("code,msg", [
    ("if cash < 2\n    invest(cash)", "end the line with ':'"),
    ("if cash < 2:\ninvest(cash)", "empty"),
    ("invest(cash", r"expected '\)'"),
    ("buy(cash)", "unknown action"),
    ("cash = 3", "built-in"),
    ("if cash <= 2:\n    invest(cash)", "only < and >"),
    ("  invest(cash)", "indent"),
    ("invest_in(cash, gold)", "not in this task"),
    ("import os", "not an action"),
])
def test_errors_name_the_line(code, msg):
    with pytest.raises(TextError, match=msg):
        to_program(code, ["cash"], ["shares", "bonds"])


@pytest.mark.parametrize("tid", sorted(RECORDS))
def test_public_tests_are_the_required_ones_plus_one_sample(tid):
    meta = RECORDS[tid]["meta"]
    pub = public_tests(meta)
    assert [t["kind"] for t in pub].count("required") == len(meta["obligatory"])
    assert [t["kind"] for t in pub].count("sample") == 1
    r = run_public(meta, RECORDS[tid]["reveal"]["reference_program"])
    assert r["required_passed"] is True and len(r["tests"]) == len(pub)
    assert r["hidden_tests"] == len(meta["optional"]) - 1
    empty = run_public(meta, {"every_month": []})
    assert empty["required_passed"] is False
