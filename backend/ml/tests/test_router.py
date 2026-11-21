"""Router tests. The persona paths were written by hand from the rules in docs/onboarding_router.md
before the code was run, so a change to rules or parameters that moves a demo path is noticed.

Revised once after the first run (2026-11-21): the hand calculation still used the old age and
education prior, which was dropped on 2026-11-20. With the flat prior the young adult's theta is
-0.18 (not -0.35), so F2 (m 0.62) is met and needs no challenge; the student's F3 (m 0.43) is a
challenge, not a full node. The demo paths themselves did not change."""
from pathlib import Path

import yaml

from router import route, tree


def k(**answers):
    """knowledge answers: Q2=(True, 4) means correct with confidence 4; None = don't know."""
    return {q: ({"correct": a[0], "confidence": a[1]} if a else {"correct": None}) for q, a in answers.items()}


YOUNG = {"age_band": "25-39", "decisions": "me", "goal": "first_investment", "horizon": "over_10",
         "self_rating": "quite_high", "buffer": "under_1", "products": ["life_insurance"],
         "knowledge": k(Q2=(True, 3), Q3=(True, 4), Q4=(False, 4), Q5=(False, 3), Q6=(False, 4))}
INVESTOR = {"age_band": "25-39", "decisions": "me", "goal": "other", "horizon": "over_10",
            "self_rating": "very_high", "buffer": "6_plus", "products": ["investment", "life_insurance", "pension"],
            "knowledge": k(Q2=(True, 5), Q3=(True, 5), Q4=(True, 4), Q5=(True, 5), Q6=(True, 5))}
STUDENT = {"age_band": "18-24", "decisions": "someone_else", "goal": "buffer", "horizon": "under_3",
           "self_rating": "quite_high", "buffer": None, "products": ["consumer_loan"],
           "knowledge": k(Q2=(False, 4), Q3=(False, 4), Q4=(False, 3), Q5=(True, 3), Q6=(False, 4))}
RETIREE = {"age_band": "55+", "decisions": "me", "goal": "retirement", "horizon": "3_10",
           "self_rating": "average", "buffer": "3_6", "products": ["life_insurance", "non_life_insurance"],
           "knowledge": k(Q2=(True, 3), Q3=(True, 4), Q4=(False, 2), Q5=(False, 3), Q6=(True, 3))}


def nodes(items):
    return [i["node"] for i in items]


def test_young_adult_demo_path():
    r = route(YOUNG)
    assert nodes(r["path"]) == ["S1", "I1", "I2", "I4", "P1"]
    assert set(nodes(r["challenges"])) == {"F1"}
    assert r["path"][0]["reason"].startswith("You said you could not cover a month")


def test_investor_demo_path():
    r = route(INVESTOR)
    assert nodes(r["path"]) == ["I4", "I5"]
    assert {"F1", "F3", "I1"} <= set(nodes(r["challenges"]))
    assert r["knowledge_score"] == 5 and r["band"] == "high"


def test_student_path():
    r = route(STUDENT)
    assert nodes(r["path"]) == ["F4", "S2"]
    assert {"F3", "S1"} <= set(nodes(r["challenges"]))


def test_pre_retiree_path_and_goal():
    r = route(RETIREE)
    assert nodes(r["path"]) == ["O1", "L1"]
    assert "S4" in nodes(r["challenges"]) and r["goal"]["node"] == "L3"


def test_skipped_questions_still_give_a_path():
    r = route({"age_band": "40-54", "goal": "other", "horizon": "3_10", "buffer": None, "products": None,
               "knowledge": k(Q2=None, Q3=None, Q4=None, Q5=None, Q6=None)})
    assert r["knowledge_score"] == 0 and r["band"] == "low" and r["path"]


def test_placement_depends_on_answers_not_on_age():
    # Decided 2026-11-20: no demographic prior. Age may change needs, never the ability estimate.
    older = dict(YOUNG, age_band="55+")
    assert route(YOUNG)["theta"] == route(older)["theta"] and route(YOUNG)["mastery"] == route(older)["mastery"]


def test_events_match_the_result():
    r = route(YOUNG, "u-1")
    types = [e["event_type"] for e in r["events"]]
    assert types.count("path_issued") == 1
    assert types.count("recommendation_shown") == len(r["path"]) and types.count("challenge_offered") == len(r["challenges"])
    assert all(0 <= e["predicted_m"] <= 1 for e in r["events"] if "predicted_m" in e)


def test_benchmarks_come_from_the_table():
    r = route(YOUNG)["benchmarks"]
    assert r["group"] == "25-39" and r["items"]["Q4"]["poland"] == 21.6 and r["items"]["Q4"]["your_age"] == 22.6


def test_tree_agrees_with_the_node_files():
    # Two sources describe prerequisites; they must not drift apart.
    content = Path(__file__).resolve().parents[2] / "content" / "nodes"
    for path in content.glob("[!_]*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        node = tree()[data["node"]]
        assert data.get("after", []) == node["after"], data["node"]
        assert data.get("title") == node["title"], data["node"]


# ---------------------------------------------------------------- demo mode

from router.demo import finished, match  # noqa: E402

BUILT = {"S1", "I1", "I2", "I4", "I5", "P1", "P2", "P4", "F1", "F2", "F3"}   # nodes with content after the demo trim


def test_demo_young_adult_gets_the_path_directly():
    d = match(route(YOUNG), BUILT)
    assert d["status"] == "ready" and d["path_id"] == "young_adult" and d["message"] is None


def test_demo_investor_router_path_extends_to_the_investor_path():
    # The router gives I4 > I5; it is part of the investor demo path, so the user gets the whole path.
    d = match(route(INVESTOR), BUILT)
    assert d["path_id"] == "investor" and d["path"] == ["I4", "I5", "P1", "P4"] and "P2" in d["challenges"]
    # Decided 2026-11-21: the young-adult capstone (P1) is optional for investors; their capstone is P4.
    assert d["hard"] == {"p1.h1": "optional", "p4.h1": "capstone"}


def test_demo_path_not_ready_offers_both_paths():
    d = match(route(STUDENT), BUILT)
    assert d["status"] == "not_ready" and d["missing"] == ["F4", "S2"]
    assert {o["id"] for o in d["options"]} == {"young_adult", "investor"} and d["closest"] == d["options"][0]["id"]
    assert "Cost of credit" in d["message"] and "not ready yet" in d["message"]


def test_finishing_offers_the_other_path_and_optional_feedback():
    f = finished("young_adult")
    assert f["other_path"]["id"] == "investor" and f["feedback"]["optional"] is True
