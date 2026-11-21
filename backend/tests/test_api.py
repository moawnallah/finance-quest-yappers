"""End-to-end API tests on a fresh temporary SQLite database (migrations + seed)."""
import json
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def _content(slice_key):
    return json.loads((BACKEND / "content" / "slices" / f"{slice_key}.json").read_text())


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "slices": 13}


def test_requires_token(client):
    r = client.get("/wheel")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_wheel(client, auth):
    sl = client.get("/wheel", headers=auth).json()["slices"]
    assert len(sl) == 13 and sl[0]["key"] == "bonds"
    stocks = next(x for x in sl if x["key"] == "stocks")
    assert stocks["highlight"] and stocks["progress"] == 0


def test_tree_states_never_locked(client, auth):
    nodes = client.get("/wheel/stocks/tree", headers=auth).json()["nodes"]
    by_id = {n["id"]: n for n in nodes}
    assert by_id["stocks.s1"]["state"] == "current" and by_id["stocks.s2"]["state"] == "ahead"
    assert by_id["stocks.s2"]["hint"].startswith("We suggest")
    assert client.get("/nodes/stocks.s2", headers=auth).status_code == 200  # skipping ahead is allowed


def test_node_hides_answers(client, auth):
    body = client.get("/nodes/stocks.s1", headers=auth).json()
    q = body["questions"][0]
    assert "answer" not in q and "why" not in q and len(q["options"]) == 3


def test_answer_flow_unlocks_next(client, auth):
    content = _content("stocks")["nodes"][0]
    wrong = (content["questions"][0]["answer"] + 1) % 3
    r = client.post("/answers", headers=auth, json={"question_id": "stocks.s1.q1", "choice": wrong}).json()
    assert r["is_correct"] is False and r["xp_awarded"] == 0 and r["node_completed"] is False
    for q in content["questions"]:
        r = client.post("/answers", headers=auth, json={"question_id": q["id"], "choice": q["answer"]}).json()
        assert r["is_correct"] is True
    assert r["node_completed"] is True and set(r["unlocked"]) == {"stocks.s2", "stocks.s3"}
    states = {n["id"]: n["state"] for n in client.get("/wheel/stocks/tree", headers=auth).json()["nodes"]}
    assert states["stocks.s1"] == "done" and states["stocks.s2"] == "current" and states["stocks.s3"] == "open"


def test_answer_ahead_allowed_and_bad_choice(client, auth):
    assert client.post("/answers", headers=auth, json={"question_id": "stocks.s5.q1", "choice": 0}).status_code == 200
    assert client.post("/answers", headers=auth, json={"question_id": "stocks.s1.q1", "choice": 9}).status_code == 422


def test_benchmark_before_and_progress(client, auth):
    qs = client.get("/benchmark?stage=before", headers=auth).json()
    assert len(qs) == 5 and all("choice" in o for o in qs[0]["options"])
    bench = json.loads((BACKEND / "content" / "eu_benchmark.json").read_text())["quiz"]
    answers = [{"question_id": q["id"], "choice": q["answer"]} for q in bench]
    r = client.post("/benchmark/answers", headers=auth, json={"stage": "before", "answers": answers}).json()
    assert r["score"] == 5 and r["band"] == "high" and "20% of Poles" in r["comparison"]
    again = client.post("/benchmark/answers", headers=auth, json={"stage": "before", "answers": answers})
    assert again.status_code == 409
    p = client.get("/me/progress", headers=auth).json()
    assert p["xp"] == 20 and p["streak_days"] == 1 and p["nodes_completed"] == 1 and p["benchmark_before"] == 5


def test_ab_results(client, auth):
    assert client.get("/admin/ab-results").status_code == 403
    assert client.get("/admin/ab-results?key=wrong").status_code == 403
    out = client.get("/admin/ab-results", headers={"X-Admin-Key": "test-admin-key"}).json()
    assert set(out) == {"A", "B"} and sum(v["users"] for v in out.values()) == 1


def test_meta_and_field_descriptions(client):
    meta = client.get("/meta").json()
    assert set(meta["node_states"]) >= {"done", "current", "open", "ahead"} and "locked" not in meta["node_states"]
    spec = client.get("/openapi.json").json()["components"]["schemas"]
    assert "description" in spec["SliceOut"]["properties"]["risk"]


def test_badges_awarded(client, auth):
    mine = {b["key"]: b for b in client.get("/me/badges", headers=auth).json()}
    assert set(mine) == {"first_step", "slice_master", "survived_2008", "above_poland", "streak_3", "streak_7"}
    assert mine["first_step"]["earned"] and mine["above_poland"]["earned"]  # node s1 done, benchmark 5/5
    assert not mine["streak_7"]["earned"] and mine["streak_7"]["awarded_at"] is None
    # choosing "hold" in the crash question earns 'Survived 2008' and returns it as a new badge
    q = next(q for n in _content("stocks")["nodes"] for q in n["questions"] if "feedback" in q)
    hold = next(i for i, o in enumerate(q["options"]) if o.lower().startswith("hold"))
    r = client.post("/answers", headers=auth, json={"question_id": q["id"], "choice": hold}).json()
    assert [b["key"] for b in r["new_badges"]] == ["survived_2008"]
    r = client.post("/answers", headers=auth, json={"question_id": q["id"], "choice": hold}).json()
    assert r["new_badges"] == []  # never awarded twice


def test_leaderboard(client, auth):
    other = client.post("/auth/session", json={"display_name": "Marek"}).json()
    board = client.get("/leaderboard", headers=auth).json()
    assert board["league"] == 1 and len(board["entries"]) == 2
    first = board["entries"][0]
    assert first["display_name"] == "Zofia" and first["is_me"] and first["weekly_xp"] > 0 and first["rank"] == 1
    assert board["entries"][1] == {"rank": 2, "display_name": "Marek", "weekly_xp": 0, "is_me": False}
    assert "user_id" not in str(board) and other["token"] not in str(board)


def test_meta_lists_badges(client):
    assert "survived_2008" in client.get("/meta").json()["badges"]


def test_admin_monitoring_endpoints(client, auth):
    """Admin views need the key in the header; LLM calls come back with masked text and pseudonymous users."""
    for path in ("/admin/summary", "/admin/events", "/admin/llm-events", "/admin/reco-events"):
        assert client.get(path).status_code == 403
        assert client.get(path, headers={"X-Admin-Key": "wrong"}).status_code == 403
    key = {"X-Admin-Key": "test-admin-key"}
    from app.admin import log_llm_event, log_reco_event
    from app.db import SessionLocal
    with SessionLocal() as db:
        log_llm_event(db, None, mode="explain_concept", intent="question", model_role="tutor_small",
                      model="ollama/gemma4:12b", latency_ms=1200, checks_failed=[], fallback_used=False,
                      flagged_for_review=False, prompt_masked="What is diversification?", answer_masked="Spreading money...")
        log_reco_event(db, None, "path_issued", router_version="v1", path=["S1", "I1"])
        db.commit()
    s = client.get("/admin/summary", headers=key).json()
    assert s["llm_calls"] >= 1 and s["reco_events"] >= 1 and s["users"] >= 1
    items = client.get("/admin/llm-events", headers=key).json()["items"]
    assert items[0]["prompt"] == "What is diversification?" and items[0]["model"] == "ollama/gemma4:12b"
    ev = client.get("/admin/events", headers=key).json()
    assert ev["items"] and all(len(i["user"] or "x" * 10) == 10 for i in ev["items"])  # pseudonymous ids only
    assert client.get("/admin/reco-events", headers=key).json()["items"][0]["path"] == ["S1", "I1"]


def test_tutor_falls_back_and_cleans_diagrams(client, auth, monkeypatch):
    """No model reachable: the stored explanation comes back and the call is logged.
    With a (fake) model: unsafe or non-Mermaid diagrams are dropped, valid ones pass."""
    from app import tutor_api
    monkeypatch.setattr(tutor_api, "OLLAMA_API_BASE", "http://127.0.0.1:9")  # nothing listens here
    ctx = {"question": "What is an emergency fund for?", "explanation": "Money kept for surprises."}
    r = client.post("/tutor", headers=auth, json={"message": "Why was I wrong?", "context": ctx}).json()
    assert r["fallback"] is True and r["text"] == "Money kept for surprises." and r["mermaid"] is None

    good = "xychart-beta\n    x-axis [2026, 2027]\n    line [1000, 1050]"
    monkeypatch.setattr(tutor_api, "call_model", lambda m: ({"text": "Here it is.", "mermaid": good}, 10, 5, 5))
    r = client.post("/tutor", headers=auth, json={"message": "Draw a line chart of compound growth"}).json()
    assert r["mermaid"] == good and r["fallback"] is False
    monkeypatch.setattr(tutor_api, "call_model", lambda m: ({"text": "x", "mermaid": "flowchart TD\n A --> B\n click A call evil()"}, 10, 5, 5))
    assert client.post("/tutor", headers=auth, json={"message": "Draw a diagram"}).json()["mermaid"] is None
    key = {"X-Admin-Key": "test-admin-key"}
    items = client.get("/admin/llm-events", headers=key).json()["items"]
    assert any("diagram_rejected" in i["checks_failed"] for i in items)
    assert tutor_api.mask("mail me at a.b@x.pl or +48 600 700 800") == "mail me at [email] or [phone]"
