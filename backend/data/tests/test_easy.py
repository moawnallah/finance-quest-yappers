import copy
import datetime as dt
import json
from pathlib import Path

import pytest

from common import AttemptError, Report, tolerance_score
from easy import (easy_done, node_view, prerequisite_passed, prerequisite_test, question_view, reveal_view,
                  score, secrets)
from easy.build import CONTENT, build, load_sources, write
from easy.node import compile_item, graph_problems, validate_card, validate_item

DATA = Path(__file__).resolve().parent.parent
TODAY = dt.date(2026, 11, 20)
SOURCES = load_sources()


@pytest.fixture(scope="module")
def built():
    return build(CONTENT, TODAY)


@pytest.fixture(scope="module")
def nodes(built):
    return built[0]


@pytest.fixture(scope="module")
def items(nodes):
    return {i["id"]: i for n in nodes.values() for i in n["items"]}


def item_errors(item, node="I4"):
    r = Report()
    validate_item(item, node, SOURCES, TODAY, r)
    return r.errors


# ---------------------------------------------------------------- build and views

def test_content_builds_and_matches_schema(built, tmp_path):
    records, reports, graph_errors, _ = built
    assert not graph_errors
    assert set(records) == set(reports), {n: r.errors for n, r in reports.items() if r.errors}
    data = json.loads(write(*built, tmp_path).read_text(encoding="utf-8"))
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(data, json.loads((DATA / "schemas" / "easy.schema.json").read_text(encoding="utf-8")))


def test_every_kind_is_used(items):
    assert {i["kind"] for i in items.values()} == {"single", "multi", "true_false", "numeric", "reflection"}


def test_views_hide_answers(nodes):
    for node in nodes.values():
        dumped = json.dumps(node_view(node))
        for secret in ('"answer"', '"why"', '"feedback"', '"tolerance"', '"checked"', '"meta"', '"reveal"'):
            assert secret not in dumped, (node["node"], secret)


def test_card_links_resolve_to_the_register(nodes):
    link = nodes["I4"]["cards"][0]["links"][0]
    assert link["id"] == "eb525_pl" and link["url"].startswith("https://")


def test_reflection_has_no_confidence(items):
    assert "confidence" not in question_view(items["i4.e3"])
    assert "confidence" in question_view(items["i4.e1"])


def test_localization():
    item = compile_item({"id": "i4.e9", "kind": "true_false", "q": {"en": "Yes?", "pl": "Tak?"},
                         "answer": True, "why": "Because."}, "I4")
    assert question_view(item, "pl")["q"] == "Tak?" and question_view(item, "de")["q"] == "Yes?"


# ---------------------------------------------------------------- scoring

def test_single_and_true_false(items):
    assert score(items["i4.e1"], 1, confidence=5)["score"] == 1.0
    assert score(items["i4.e1"], 0)["score"] == 0.0
    assert score(items["i4.e2"], False)["score"] == 1.0
    s = score(items["i4.e2"], True, confidence=3)
    assert s["score"] == 0.0 and s["p"] == 0.5 and s["level"] == "easy"


def test_multi_formula(items):
    item = items["i1.e3"]  # correct: 0, 2, 3
    assert score(item, [0, 2, 3])["score"] == 1.0
    assert score(item, [0, 2])["score"] == pytest.approx(2 / 3, abs=1e-4)
    assert score(item, [0, 1, 2, 3])["score"] == pytest.approx(2 / 3, abs=1e-4)  # (3 - 1) / 3
    assert score(item, [1])["score"] == 0.0                              # clipped
    assert score(item, [])["score"] == 0.0


def test_tolerance_rule_matches_the_spec_example():
    # Spec: t = 30,000, band 10%, so d = 3,000.
    assert tolerance_score(32000, 30000, "relative", 0.10) == 1.0
    assert tolerance_score(36000, 30000, "relative", 0.10) == pytest.approx(0.5)
    assert tolerance_score(40000, 30000, "relative", 0.10) == 0.0
    assert tolerance_score(5, 5, "absolute", 0) == 1.0 and tolerance_score(5.1, 5, "absolute", 0) == 0.0


def test_numeric(items):
    item = items["s1.e2"]  # 14,400 PLN, absolute band 100
    assert score(item, 14400)["score"] == 1.0
    assert score(item, 14550)["score"] == pytest.approx(0.75)
    assert score(item, 20000)["score"] == 0.0


def test_reflection_is_not_scored(items):
    s = score(items["i4.e3"], 1, confidence=4)
    assert s["score"] is None and s["confidence"] is None and s["p"] is None
    assert len(reveal_view(items["i4.e3"])["feedback"]) == 3


@pytest.mark.parametrize("item_id, response, confidence", [
    ("i4.e1", 3, None), ("i4.e1", True, None), ("i4.e2", "yes", None),
    ("i1.e3", [0, 0], None), ("i1.e3", 0, None), ("s1.e2", "14400", None), ("i4.e1", 1, 0),
])
def test_bad_answers_raise(items, item_id, response, confidence):
    with pytest.raises(AttemptError):
        score(items[item_id], response, confidence)


def test_secrets_for_the_tutor(items):
    assert secrets(items["i4.e1"])["strings"] == [items["i4.e1"]["question"]["options"][1]]
    assert secrets(items["s1.e2"]) == {"strings": [], "numbers": [14400]}
    assert len(secrets(items["i1.e3"])["strings"]) == 3


# ---------------------------------------------------------------- prerequisite test and completion

def test_prerequisite_test_is_deterministic_and_uses_check_items(nodes):
    a = prerequisite_test(nodes, "P1", seed="user-1")
    assert a == prerequisite_test(nodes, "P1", seed="user-1")
    assert len(a) == 3 and len(set(a)) == 3
    by_id = {i["id"]: i for n in nodes.values() for i in n["items"]}
    assert all(by_id[i]["check"] and by_id[i]["node"] in ("I2", "I4") for i in a)
    assert {by_id[i]["node"] for i in a} == {"I2", "I4"}  # spread over both prerequisites


def test_prerequisite_test_with_missing_prerequisite_is_empty(nodes):
    without_f2 = {k: v for k, v in nodes.items() if k != "F2"}  # as if F2 had no node file
    assert prerequisite_test(without_f2, "D3", seed=1) == []


def test_completion_rule():
    assert prerequisite_passed([1, 1]) and not prerequisite_passed([1, 0]) and not prerequisite_passed([])
    assert easy_done([1, 1], [])
    assert easy_done([1, 0], [1, 0.5, 0.5]) is False   # failed test, items average 0.67
    assert easy_done([1, 0], [1, 1, 0.5]) is True    # items average 0.83
    assert easy_done([], [1, 0.8, 0.7]) is True


def test_passed_challenge_completes_the_node():
    # Decided 2026-11-21: a passed test-out ("challenge") completes the whole node, so a known
    # node does not demand a medium task; a failed one leaves the normal rule in place.
    assert node_done(False, [], test_out_scores=[1, 1]) is True
    assert node_done(False, [], test_out_scores=[1, 0]) is False
    assert node_done(True, [0.7], test_out_scores=[1, 0]) is True


# ---------------------------------------------------------------- validation

BASE = {"id": "i4.e9", "kind": "single", "q": "Q?", "options": ["a", "b", "c"], "answer": 1, "why": "Because."}


@pytest.mark.parametrize("change, message", [
    ({"id": "x.e1"}, "must look like"),
    ({"kind": "matching"}, "kind"),
    ({"answer": 3}, "index"),
    ({"options": ["only one"]}, "2-6 texts"),
    ({"why": None}, "why is required"),
    ({"kind": "multi", "answer": [0, 0]}, "distinct"),
    ({"kind": "true_false", "answer": 1}, "true or false"),
    ({"kind": "numeric", "answer": 10, "unit": "PLN", "tolerance": {"kind": "fuzzy", "band": 1}}, "tolerance"),
    ({"kind": "numeric", "answer": 10, "unit": "PLN", "tolerance": {"kind": "absolute", "band": 1},
      "input": {"min": 20, "max": 30, "step": 1}}, "outside input"),
    ({"kind": "reflection", "answer": None, "feedback": ["x"]}, "one text per option"),
    ({"kind": "reflection", "feedback": ["x", "y", "z"], "check": True}, "can't be a check item"),
    ({"sources": ["nope"]}, "unknown source"),
    ({"valid_until": "2020-01-01"}, "in the past"),
])
def test_item_validation(change, message):
    item = {**copy.deepcopy(BASE), **change}
    if item["kind"] == "reflection" and item.get("answer", 1) is None:
        del item["answer"]
    if item["kind"] == "reflection" and "feedback" in item and len(item["feedback"]) == 3:
        del item["answer"]
    errors = item_errors(item)
    assert any(message in e for e in errors), errors


def test_valid_item_has_no_errors():
    assert item_errors(copy.deepcopy(BASE)) == []


def test_card_validation():
    r = Report()
    validate_card({"id": "i4.c9", "title": "T", "body": "word " * 81, "links": ["nope", "eb525_pl", "damodaran_histret"]},
                  "I4", SOURCES, TODAY, r)
    assert any("81 words" in e for e in r.errors) and any("unknown source" in e for e in r.errors)
    assert any("3 links" in w for w in r.warnings) and any("no example" in w for w in r.warnings)


def test_graph_cycle_and_missing_node():
    errors, warnings = graph_problems({"A1": {"after": ["B1"]}, "B1": {"after": ["A1", "Z9"]}})
    assert any("cycle" in e for e in errors) and any("Z9" in w for w in warnings)


# ---------------------------------------------------------------- added after the spec review

from easy import node_done                      # noqa: E402
from easy import test_out as draw_test_out      # aliased, so pytest doesn't collect it as a test


def test_test_out_uses_the_nodes_own_check_items(nodes):
    ids = draw_test_out(nodes, "I4", seed="user-1")
    assert ids == draw_test_out(nodes, "I4", seed="user-1") and len(ids) == 2
    own_checks = {i["id"] for i in nodes["I4"]["items"] if i["check"]}
    assert set(ids) <= own_checks


def test_node_done_needs_a_medium_task():
    assert node_done(True, [0.6]) and not node_done(True, [0.59]) and not node_done(True, [])
    assert not node_done(False, [1.0])


def test_easy_attempt_has_the_same_columns_as_medium(items):
    s = score(items["i4.e1"], 1)
    assert {"score_estimate", "score_reasons", "score"} <= set(s) and s["score_estimate"] is None
