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
    r = client.get("/tasks/p1.h1", headers=user).json()
    dumped = json.dumps(r)
    assert r["level"] == "hard" and "blockly" in r["task"]
    assert "reference_program" not in dumped and "editorial" not in dumped and '"meta"' not in dumped


def test_hard_task_scoring_through_the_api(client, user):
    starter = client.get("/tasks/p1.h1", headers=user).json()["task"]["blockly"]["starter"]
    bad = client.post("/tasks/p1.h1/attempts", headers=user, json={"response": starter, "confidence": 3}).json()
    assert bad["accepted"] is False and bad["points"] is None and bad["reveal"]["result"]["story"]
    good = client.post("/tasks/p1.h1/attempts", headers=user,
                       json={"response": HARD["p1.h1"]["reveal"]["reference_workspace"], "confidence": 4}).json()
    assert good["accepted"] is True and good["points"] == 95 and good["growth_index"] == 100.0
    hard = client.get("/admin/items", headers=ADMIN).json()["hard"]
    cap = next(h for h in hard if h["task_id"] == "p1.h1")
    assert cap["most_failed_test"].startswith("A 2-month job loss") and cap["duration_ms_p50"] is not None


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
    assert client.post("/study/join", headers=ADMIN, json={"consent": False}).status_code == 400
    j = client.post("/study/join", headers=ADMIN, json={"consent": True}).json()
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
    client.post("/tasks/p1.h1/attempts", headers=user,
                json={"response": HARD["p1.h1"]["reveal"]["reference_workspace"], "confidence": 4})
    s = client.get("/me/summary", headers=user).json()
    assert s["path"][0]["node"] == "S1" and s["hard"]["p1.h1"]["best_points"] == 95
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


def test_study_join_needs_a_key(client):
    assert client.post("/study/join", json={"consent": True}).status_code == 403
    assert client.post("/study/join", headers={"X-Study-Key": "wrong"}, json={"consent": True}).status_code == 403
    assert client.post("/study/join", headers=ADMIN, json={"consent": True}).status_code == 200


def test_withdrawal_deletes_every_row_of_the_participant(client):
    from app.db import SessionLocal
    from app.models import Consent, Event, Feedback, LlmEvent, Onboarding, RecoEvent, User
    j = client.post("/study/join", headers=ADMIN, json={"consent": True}).json()
    h = {"Authorization": f"Bearer {j['token']}"}
    client.post("/onboarding", headers=h, json=YOUNG)
    client.post("/feedback", headers=h, json={"where": "item", "target_id": "i1.e1", "kind": "unclear", "text": "my name is Zofia"})
    client.post("/events/node-opened", headers=h, json={"node": "S1", "source": "self_chosen"})
    with SessionLocal() as db:
        db.add(LlmEvent(user_id=j["user_id"], prompt_masked="a question", checks_failed=[], fallback_used=False,
                        flagged_for_review=False))
        db.commit()
    uid = j["user_id"]
    models = (Feedback, LlmEvent, RecoEvent, Event, Onboarding, Consent)
    with SessionLocal() as db:
        assert all(db.query(m).filter(m.user_id == uid).count() > 0 for m in models)
        texts_before = db.query(Feedback).filter(Feedback.text.isnot(None)).count()
        prompts_before = db.query(LlmEvent).filter(LlmEvent.prompt_masked.isnot(None)).count()
    assert client.delete(f"/admin/study/{j['participant_id']}", headers=ADMIN).status_code == 200
    with SessionLocal() as db:
        assert db.get(User, uid) is None
        assert all(db.query(m).filter(m.user_id == uid).count() == 0 for m in models)
        # nothing was kept as an orphan with the user id blanked
        assert db.query(Feedback).filter(Feedback.text.isnot(None)).count() == texts_before - 1
        assert db.query(LlmEvent).filter(LlmEvent.prompt_masked.isnot(None)).count() == prompts_before - 1


def test_survey_rejects_invalid_knowledge_values(client, user):
    base = {k: v for k, v in YOUNG.items() if k != "knowledge"}
    for bad in ({"Q2": {"correct": False, "confidence": "high"}}, {"Q2": {"correct": False, "confidence": 99}},
                {"Q2": {"correct": False, "confidence": 0}}, {"Q2": {"correct": "yes", "confidence": 3}},
                {"Q9": {"correct": True}}):
        assert client.post("/onboarding", headers=user, json={**base, "knowledge": bad}).status_code == 422, bad
    ok = {"Q2": {"correct": None}, "Q3": {"correct": True, "confidence": 5}}
    assert client.post("/onboarding", headers=user, json={**base, "knowledge": ok}).status_code == 200


def test_unknown_path_and_node_are_rejected(client, user):
    assert client.post("/paths/finish", headers=user, json={"path_id": "does_not_exist", "progress": "yes",
                                                            "next_goal": "other"}).status_code == 400
    assert client.post("/events/node-opened", headers=user, json={"node": "ZZ", "source": "self_chosen"}).status_code == 404


def test_roadmap_lists_built_and_planned_nodes(client):
    nodes = client.get("/roadmap").json()["nodes"]
    assert len(nodes) == 32
    assert any(n["live"] for n in nodes) and any(not n["live"] for n in nodes)
    assert {"id", "title", "panel", "after", "live"} <= set(nodes[0])


def test_my_path_follows_the_survey(client, user):
    assert client.get("/me/path", headers=user).json() == {"survey_done": False, "steps": [], "challenges": []}
    client.post("/onboarding", headers=user, json=YOUNG)
    p = client.get("/me/path", headers=user).json()
    assert p["survey_done"] is True and p["steps"] and p["source"] in ("recommended", "demo", "personal", "chosen")
    assert all({"node", "title", "live", "done"} <= set(s) for s in p["steps"])
    if p["options"]:
        client.post("/onboarding/choose-path", headers=user, json={"path_id": p["options"][0]["id"]})
        q = client.get("/me/path", headers=user).json()
        assert q["source"] == "chosen" and [s["node"] for s in q["steps"]] == p["options"][0]["nodes"]


# ---------------------------------------------------------------- router rules-2 (2026-11-21)

APP_SURVEY = {"age_band": "18-24", "goal": "first_investment", "horizon": "3_10", "self_rating": "average",
              "experience": "none"}   # what the app's onboarding screens collect before the quick check


def test_survey_without_the_quick_check_still_builds_a_path(client, user):
    # The app lets users skip the quick check; until now that sent nothing, and the Path tab stayed empty.
    r = client.post("/onboarding", headers=user, json=APP_SURVEY).json()
    assert r["knowledge_score"] is None and r["items_answered"] == 0 and len(r["path"]) >= 3


def test_switching_to_a_ready_path_keeps_the_recommended_one(client, user):
    # "Change plan" to a predefined path and back: the survey's path is stored, not overwritten.
    first = client.post("/onboarding", headers=user, json=STUDENT).json()["path"]
    client.post("/onboarding/choose-path", headers=user, json={"path_id": "investor"})
    assert client.get("/me/path", headers=user).json()["source"] == "chosen"
    back = client.post("/onboarding/choose-path", headers=user, json={"path_id": "recommended"}).json()
    assert back["nodes"] == [p["node"] for p in first]
    assert [s["node"] for s in client.get("/me/path", headers=user).json()["steps"]] == back["nodes"]


def test_finishing_a_path_suggests_next_nodes(client, user):
    client.post("/onboarding", headers=user, json=YOUNG)
    end = client.post("/paths/finish", headers=user, json={"path_id": "young_adult", "progress": "yes",
                                                            "next_goal": "keep_learning"}).json()
    assert len(end["next_steps"]) == 3 and all({"node", "title", "reason", "live"} <= set(x) for x in end["next_steps"])
    events = client.get("/admin/reco-events", params={"event_type": "next_steps_shown"}, headers=ADMIN).json()["items"]
    assert events and events[0]["path"] == [x["node"] for x in end["next_steps"]]


def test_shadow_model_is_logged_and_never_breaks_onboarding(client, user, monkeypatch):
    # BASAL runs in shadow mode: its answers are stored, an outage costs nothing but an error row.
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import RecoEvent
    from router import shadow
    monkeypatch.setenv("BASAL_URL", "http://basal.test")
    fake = {"model": "basal-2.0-4.5B", "answers": {"start_S1": {"type": "noul", "noul": 0.9, "confidence": 0.9},
                                                   "ready_S1": {"type": "noul", "noul": 0.3, "confidence": 0.7}}}
    monkeypatch.setattr(shadow, "ask", lambda request, base_url: (fake, 120))
    path = client.post("/onboarding", headers=user, json=YOUNG).json()["path"]

    def boom(request, base_url):
        raise TimeoutError("no GPU")
    monkeypatch.setattr(shadow, "ask", boom)
    assert client.post("/onboarding", headers=user, json=YOUNG).json()["path"] == path
    with SessionLocal() as db:
        rows = [r.payload for r in db.scalars(select(RecoEvent).where(RecoEvent.event_type == "shadow_decision")
                                              .order_by(RecoEvent.id.desc()).limit(2))]
    assert "TimeoutError" in rows[0]["error"]
    assert rows[1]["decisions"] == [{"node": "S1", "router_m": rows[1]["decisions"][0]["router_m"], "on_path": True,
                                     "ready_p": 0.3, "start_p": 0.9, "start_confidence": 0.9, "agrees": True,
                                     "below_tau": False}]
