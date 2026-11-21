"""Onboarding, hard tasks, the challenge rule, feedback, study mode and admin views through the API
(docs/admin_and_profile.md). Each test checks one promise the demo or the hallway test relies on."""
import json
import re
from pathlib import Path

import pytest

OUTPUT = Path(__file__).resolve().parent.parent / "data" / "output"
ITEMS = {i["id"]: i for n in json.loads((OUTPUT / "easy.json").read_text(encoding="utf-8"))["nodes"] for i in n["items"]}
HARD = {t["id"]: t for t in json.loads((OUTPUT / "hard_tasks.json").read_text(encoding="utf-8"))["tasks"]}
ADMIN = {"X-Admin-Key": "test-admin-key"}

YOUNG = {"age_band": "25-39", "decisions": "me", "goal": "first_investment", "horizon": "over_10",
         "self_rating": "quite_high", "buffer": "under_1", "products": ["life_insurance"],
         "knowledge": {"Q2": {"correct": True, "confidence": 3}, "Q3": {"correct": True, "confidence": 4},
                       "Q4": {"correct": False, "confidence": 4}, "Q5": {"correct": False, "confidence": 3},
                       "Q6": {"correct": False, "confidence": 4}}}


@pytest.fixture()
def user(client):
    token = client.post("/auth/session", json={"display_name": "Test"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_onboarding_gives_the_demo_path_and_logs_events(client, user):
    r = client.post("/onboarding", headers=user, json=YOUNG)
    assert r.status_code == 200
    assert [p["node"] for p in r.json()["path"]] == ["S1", "I1", "I2", "I4", "P1"]
    events = client.get("/admin/reco-events", headers=ADMIN).json()["items"]   # Mo's route
    assert any(e["type"] == "path_issued" and e["path"][0] == "S1" for e in events)


def test_hard_task_view_hides_the_solution(client, user):
    r = client.get("/tasks/s1.h1", headers=user).json()
    dumped = json.dumps(r)
    assert r["level"] == "hard" and "blockly" in r["task"]
    assert "reference_program" not in dumped and "editorial" not in dumped and '"meta"' not in dumped


def test_hard_task_scoring_through_the_api(client, user):
    starter = client.get("/tasks/s1.h1", headers=user).json()["task"]["blockly"]["starter"]
    bad = client.post("/tasks/s1.h1/attempts", headers=user, json={"response": starter, "confidence": 3}).json()
    assert bad["accepted"] is False and bad["points"] is None and bad["reveal"]["result"]["story"]
    good = client.post("/tasks/s1.h1/attempts", headers=user,
                       json={"response": HARD["s1.h1"]["reveal"]["reference_workspace"], "confidence": 4}).json()
    assert good["accepted"] is True and good["points"] == 97 and good["growth_index"] == 100.0
    hard = client.get("/admin/items", headers=ADMIN).json()["hard"]
    s1 = next(h for h in hard if h["task_id"] == "s1.h1")
    assert s1["most_failed_test"].startswith("Job loss") and s1["duration_ms_p50"] is not None


def test_passed_challenge_completes_the_node(client, user):
    # Decided 2026-11-21: a passed test-out completes the whole node, even one with a medium task (I2).
    items = client.get("/skills/I2/test-out", headers=user).json()["items"]
    assert items
    status = None
    for it in items:
        r = client.post(f"/tasks/{it['id']}/attempts", headers=user,
                        json={"response": ITEMS[it["id"]]["reveal"]["answer"], "confidence": 4,
                              "context": "test_out", "for_node": "I2"})
        status = r.json()["status"]
    assert status["done"] is True and status["test_out"]["passed"] is True


def test_two_wrong_fact_reports_raise_a_red_alert(client, user):
    for _ in range(2):
        assert client.post("/feedback", headers=user, json={"where": "item", "target_id": "i2.e3",
                                                            "kind": "wrong_fact", "text": "mail me at a@b.pl"}).status_code == 200
    fb = client.get("/admin/feedback", headers=ADMIN).json()
    assert {"target_id": "i2.e3", "open_wrong_fact_reports": 2, "level": "red"} in fb["alerts"]
    assert all("a@b.pl" not in (r["text"] or "") for r in fb["reports"])   # personal data masked
    assert any(a["kind"] == "report" for a in client.get("/admin/overview", headers=ADMIN).json()["alerts"])
    for r in fb["reports"]:
        if r["target_id"] == "i2.e3":
            client.patch(f"/admin/feedback/{r['id']}", headers=ADMIN, json={"status": "fixed"})
    assert client.get("/admin/feedback", headers=ADMIN).json()["alerts"] == []


def test_study_join_and_withdraw(client):
    assert client.post("/study/join", json={"consent": False}).status_code == 400
    j = client.post("/study/join", json={"consent": True}).json()
    assert re.fullmatch(r"FQ-[2-9A-HJ-NP-Z]{4}", j["participant_id"])
    h = {"Authorization": f"Bearer {j['token']}"}
    assert client.get("/me/summary", headers=h).status_code == 200
    assert client.get("/admin/study", headers=ADMIN).json()["participants"] >= 1
    assert client.delete(f"/admin/study/{j['participant_id']}", headers=ADMIN).status_code == 200
    assert client.get("/me/summary", headers=h).status_code == 401   # everything for that code is gone


def test_admin_routes_need_the_key(client):
    for path in ("/admin/overview", "/admin/items", "/admin/calibration", "/admin/advice-watch", "/admin/study"):
        assert client.get(path).status_code == 403


def test_profile_summary_and_node_clicks(client, user):
    client.post("/onboarding", headers=user, json=YOUNG)
    client.post("/tasks/s1.h1/attempts", headers=user,
                json={"response": HARD["s1.h1"]["reveal"]["reference_workspace"], "confidence": 4})
    s = client.get("/me/summary", headers=user).json()
    assert s["path"][0]["node"] == "S1" and s["hard"]["s1.h1"]["best_points"] == 97
    assert {p["panel"] for p in s["panels"]} >= {"FOUNDATIONS", "SAFETY"}
    client.post("/events/node-opened", headers=user, json={"node": "O1", "source": "self_chosen"})
    client.post("/events/node-opened", headers=user, json={"node": "S1", "source": "recommended"})
    clicks = client.get("/admin/node-opened", headers=ADMIN).json()
    assert clicks["by_source"]["self_chosen"] >= 1 and 0 < clicks["self_chosen_share"] < 1


STUDENT = {"age_band": "18-24", "decisions": "someone_else", "goal": "buffer", "horizon": "under_3",
           "self_rating": "quite_high", "buffer": None, "products": ["consumer_loan"],
           "knowledge": {"Q2": {"correct": False, "confidence": 4}, "Q3": {"correct": False, "confidence": 4},
                         "Q4": {"correct": False, "confidence": 3}, "Q5": {"correct": True, "confidence": 3},
                         "Q6": {"correct": False, "confidence": 4}}}


def test_demo_not_ready_then_choose_and_finish(client, user):
    d = client.post("/onboarding", headers=user, json=STUDENT).json()["demo"]
    assert d["status"] == "not_ready" and "not ready yet" in d["message"] and len(d["options"]) == 2
    chosen = client.post("/onboarding/choose-path", headers=user, json={"path_id": d["closest"]}).json()
    assert chosen["nodes"][0] in ("S1", "I4")
    assert client.post("/onboarding/choose-path", headers=user, json={"path_id": "nope"}).status_code == 400
    end = client.post("/paths/finish", headers=user, json={"path_id": d["closest"], "progress": "somewhat",
                                                            "confidence": {"S1": 4}, "next_goal": "keep_learning"}).json()
    assert end["other_path"]["id"] != d["closest"] and end["feedback"]["optional"] is True
    events = client.get("/admin/reco-events", params={"limit": 500}, headers=ADMIN).json()["items"]
    assert {"path_chosen", "path_finished", "demo_match"} <= {e["type"] for e in events}


def test_client_insights_are_aggregate_only(client):
    first = client.get("/admin/client-insights", headers=ADMIN).json()
    for _ in range(6):   # enough users that the young-adult group is no longer hidden
        t = client.post("/auth/session", json={"display_name": "C"}).json()["token"]
        client.post("/onboarding", headers={"Authorization": f"Bearer {t}"}, json=YOUNG)
    r = client.get("/admin/client-insights", headers=ADMIN).json()
    assert r["hidden"] is False and r["users"] >= 6 and r["profile"]["age_band"]["25-39"] is not None
    assert "user_id" not in json.dumps(r) and first["users"] < r["users"]
