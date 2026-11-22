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
    client.post("/auth/session", json={"display_name": "A guest"})  # guests are never ranked
    other = client.post("/auth/register", json={"email": "marek@example.com", "password": "a-long-password",
                                                "display_name": "Marek"}).json()
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


def test_tutor_stream_falls_back_when_no_model(client, auth, monkeypatch):
    from app import tutor_api
    monkeypatch.setattr(tutor_api, "OLLAMA_API_BASE", "http://127.0.0.1:9")
    import json as _json
    r = client.post("/tutor/stream", headers=auth, json={"message": "Why?", "context": {"explanation": "Stored text."}})
    lines = [_json.loads(l) for l in r.text.splitlines() if l.strip()]
    assert lines[-1]["t"] == "done" and lines[-1]["fallback"] is True and lines[-1]["text"] == "Stored text."


def test_accounts_register_login_and_admin(client):
    """Email accounts: passwords stored only as scrypt hashes; login checks them; admins by email."""
    from app.db import SessionLocal
    from app.models import User
    # an account always starts fresh: nothing carries over from an earlier session
    anon = client.post("/auth/session", json={"display_name": "Zofia"}).json()
    r = client.post("/auth/register", headers={"Authorization": f"Bearer {anon['token']}"},
                    json={"email": "Zofia@Example.com", "password": "correct horse 1"})
    assert r.status_code == 201 and r.json()["user_id"] != anon["user_id"] and r.json()["email"] == "zofia@example.com"
    assert r.json()["is_admin"] is False
    with SessionLocal() as db:
        u = db.get(User, r.json()["user_id"])
        assert u.password_hash.startswith("scrypt$") and "correct horse 1" not in u.password_hash
    assert client.post("/auth/register", json={"email": "zofia@example.com", "password": "another pass"}).status_code == 409
    assert client.post("/auth/register", json={"email": "not-an-email", "password": "long enough"}).status_code == 422
    assert client.post("/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422
    ok = client.post("/auth/login", json={"email": "ZOFIA@example.com", "password": "correct horse 1"})
    assert ok.status_code == 200 and ok.json()["token"] == r.json()["token"]
    bad = client.post("/auth/login", json={"email": "zofia@example.com", "password": "wrong"})
    nobody = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert bad.status_code == nobody.status_code == 401 and bad.json()["error"]["message"] == nobody.json()["error"]["message"]
    # admin accounts can open admin endpoints with their own token
    adm = client.post("/auth/register", json={"email": "admin@crocoash.xyz", "password": "admin pass 123"}).json()
    assert adm["is_admin"] is True
    assert client.get("/admin/summary", headers={"Authorization": f"Bearer {adm['token']}"}).status_code == 200
    assert client.get("/admin/summary", headers={"Authorization": f"Bearer {anon['token']}"}).status_code == 403
    assert client.get("/me", headers={"Authorization": f"Bearer {adm['token']}"}).json()["email"] == "admin@crocoash.xyz"


def test_scales_are_kept_on_the_server_and_leagues_are_real(client):
    from app.engines import catalog
    a = client.post("/auth/register", json={"email": "zofia.nowak@example.com", "password": "a-long-password"}).json()
    h = {"Authorization": f"Bearer {a['token']}"}
    assert client.get("/me/scales", headers=h).json() == {"scales": 0, "level": "Beginner"}
    item = next(i for i in catalog().items.values() if i["kind"] == "single" and i["scored"])
    right = item["reveal"]["answer"]
    r = client.post(f"/tasks/{item['id']}/attempts", headers=h, json={"response": right, "confidence": 4}).json()
    assert r["score"] == 1 and r["scales_total"] >= 10
    again = client.post(f"/tasks/{item['id']}/attempts", headers=h, json={"response": right, "confidence": 4}).json()
    assert again["scales_total"] == r["scales_total"]  # a task pays once
    d1 = client.post("/me/scales", headers=h, json={"source": "daily_right"}).json()
    d2 = client.post("/me/scales", headers=h, json={"source": "daily_tried"}).json()
    assert d1["awarded"] == 15 and d2["awarded"] == 0  # one daily scenario a day
    assert client.post("/me/scales", headers=h, json={"source": "bonus"}).status_code == 422
    lg = client.get("/leagues", headers=h).json()
    assert [l["name"] for l in lg["levels"]] == ["Beginner", "Intermediate", "Expert"]
    me = [e for l in lg["levels"] for e in l["entries"] if e["is_me"]]
    assert len(me) == 1 and me[0]["scales"] == lg["me"]["scales"] == d1["scales"]


def test_hard_task_code_panel_run_and_submit(client):
    from app.engines import catalog
    from hard.text import to_text
    h = {"Authorization": f"Bearer {client.post('/auth/session', json={'display_name': 'coder'}).json()['token']}"}
    tid = sorted(catalog().hard_tasks)[0]
    view = client.get(f"/tasks/{tid}", headers=h).json()["task"]
    panel = view["code"]
    assert [t["kind"] for t in panel["public_tests"]].count("sample") == 1 and panel["hidden_tests"] >= 1
    assert panel["starter"] and panel["values"] and panel["actions"]
    # bad code: a clear 400 with the line number
    r = client.post(f"/tasks/{tid}/run", headers=h, json={"code": "if cash < 2\n    invest(cash)"})
    assert r.status_code == 400 and "line 1" in r.json()["error"]["message"]
    # the reference solution passes the public tests; running stores no attempt
    code = to_text(catalog().hard_tasks[tid]["reveal"]["reference_program"])
    run = client.post(f"/tasks/{tid}/run", headers=h, json={"code": code}).json()
    assert run["required_passed"] is True and len(run["tests"]) == len(panel["public_tests"])
    assert "optional" not in run and "futures" not in run  # hidden results only on submit
    sub = client.post(f"/tasks/{tid}/attempts", headers=h, json={"response": {"code": code}}).json()
    assert sub["accepted"] is True and 51 <= sub["points"] <= 100
    assert len(sub["reveal"]["result"]["optional"]) == panel["hidden_tests"] + 1


def test_guests_are_not_ranked_in_leagues(client):
    from app.engines import catalog
    item = next(i for i in catalog().items.values() if i["kind"] == "single" and i["scored"])
    g = {"Authorization": f"Bearer {client.post('/auth/session', json={'display_name': 'Some guest'}).json()['token']}"}
    client.post(f"/tasks/{item['id']}/attempts", headers=g, json={"response": item["reveal"]["answer"]})
    a = client.post("/auth/register", json={"email": "ranked@example.com", "password": "a-long-password", "display_name": "Ranked"}).json()
    h = {"Authorization": f"Bearer {a['token']}"}
    client.post(f"/tasks/{item['id']}/attempts", headers=h, json={"response": item["reveal"]["answer"]})
    names = lambda hdr: [e["display_name"] for l in client.get("/leagues", headers=hdr).json()["levels"] for e in l["entries"]]
    assert "Ranked" in names(h) and "Some guest" not in names(h)
    seen_by_guest = names(g)
    assert "Some guest" in seen_by_guest and seen_by_guest.count("Some guest") == 1  # only their own row



def test_guests_are_stateless(client):
    """No token: the server scores and computes from the app's history, and stores nothing."""
    import json
    from app.db import SessionLocal
    from app.engines import catalog
    from app.models import Attempt, Event, User
    with SessionLocal() as db:
        before = (db.query(User).count(), db.query(Attempt).count(), db.query(Event).count())
    g = {"X-Guest-Id": "abcd1234-test"}
    skills = client.get("/skills", headers=g).json()
    assert skills and all(not k["status"]["done"] for k in skills)
    node = next(k for k in skills if k["items"] >= 2)["id"]
    items = [i for i in catalog().nodes[node]["items"] if i["scored"]]
    history = []
    for it in items:
        r = client.post(f"/tasks/{it['id']}/attempts", headers={**g, "X-Guest-History": json.dumps(history)},
                        json={"response": it["reveal"]["answer"], "confidence": 4}).json()
        assert r["score"] == 1 and r["record"][0] == it["id"] and r["attempt_id"] == 0
        history.append(r["record"])
    st = client.get(f"/skills/{node}", headers={**g, "X-Guest-History": json.dumps(history)}).json()["status"]
    assert st["items_answered"] == len(items)
    survey = {"age_band": "25-39", "goal": "buffer", "horizon": "3_10", "knowledge": {"Q2": {"correct": True}}}
    assert client.post("/onboarding", headers=g, json=survey).json()["path"]
    p = client.post("/path/preview", headers={**g, "X-Guest-History": json.dumps(history)}, json={"survey": survey}).json()
    assert p["survey_done"] is True and p["steps"]
    lg = client.get("/leagues", headers={**g, "X-Guest-Scales": "40"}).json()
    assert lg["me"]["scales"] == 40 and sum(e["is_me"] for l in lg["levels"] for e in l["entries"]) == 1
    with SessionLocal() as db:
        assert (db.query(User).count(), db.query(Attempt).count(), db.query(Event).count()) == before
    assert client.get("/me", headers=g).status_code == 401  # account-only routes still need a token



def test_test_out_is_one_attempt_and_completes_the_node(client, auth):
    from app.engines import catalog
    cat = catalog()
    node = next(n for n in cat.nodes if len(client.get(f"/skills/{n}/test-out", headers=auth).json()["items"]) == 2)
    items = client.get(f"/skills/{node}/test-out", headers=auth).json()["items"]
    for it in items:
        right = cat.items[it["id"]]["reveal"]["answer"]
        r = client.post(f"/tasks/{it['id']}/attempts", headers=auth,
                        json={"response": right, "context": "test_out", "for_node": node})
        assert r.status_code == 200
    assert r.json()["status"]["done"] is True and r.json()["status"]["test_out"]["passed"] is True
    again = client.post(f"/tasks/{items[0]['id']}/attempts", headers=auth,
                        json={"response": cat.items[items[0]["id"]]["reveal"]["answer"], "context": "test_out", "for_node": node})
    assert again.status_code == 409



def test_hard_code_deep_nesting_is_400_and_runs_are_rate_limited(client):
    from app import tasks_api
    from app.engines import catalog
    h = {"Authorization": f"Bearer {client.post('/auth/session', json={'display_name': 'hostile'}).json()['token']}"}
    tid = sorted(catalog().hard_tasks)[0]
    for code in ["invest_in(" + "(" * 3000 + "cash" + ")" * 3000 + ", fund)", "x = " + "-" * 3000 + "1"]:
        r = client.post(f"/tasks/{tid}/run", headers=h, json={"code": code[:8000]})
        assert r.status_code == 400, r.text
    tasks_api._RATE.clear()
    codes = [client.post(f"/tasks/{tid}/run", headers=h, json={"code": "x = 1"}).status_code for _ in range(tasks_api.HARD_LIMITS["run"] + 1)]
    assert codes[-1] == 429 and 429 not in codes[:-1]
    tasks_api._RATE.clear()


def test_tutor_cache_serves_the_second_identical_question(client, monkeypatch):
    from app import tutor_api
    calls = []
    monkeypatch.setattr(tutor_api, "TUTOR_ENABLED", True)
    monkeypatch.setattr(tutor_api.tutor_pipeline, "handles", lambda mode: False)
    def fake(messages):
        calls.append(1)
        tutor_api._last.timings = {"load_ms": 1500, "prompt_eval_ms": 40, "eval_ms": 900}
        return {"text": "An index fund holds many shares at once. Which part should we look at next?", "mermaid": None}, 1200, 50, 30
    monkeypatch.setattr(tutor_api, "call_model", fake)
    h = {"Authorization": f"Bearer {client.post('/auth/session', json={'display_name': 'cache'}).json()['token']}"}
    q = {"mode": "explain_concept", "message": "What is an index fund?", "context": {"node": "I4"}}
    a = client.post("/tutor", headers=h, json=q).json()
    b = client.post("/tutor", headers=h, json={**q, "message": "what is an   index fund?"}).json()
    assert len(calls) == 1 and b.get("cached") is True and b["text"] == a["text"]
    client.post("/tutor", headers=h, json={**q, "mode": "explain_result"})  # never cached
    client.post("/tutor", headers=h, json={**q, "history": [{"role": "user", "text": "hi"}]})  # history: never cached
    assert len(calls) == 3
    ADMIN = {"X-Admin-Key": "test-admin-key"}
    m = {x["mode"]: x for x in client.get("/admin/tutor-metrics", headers=ADMIN).json()["modes"]}
    assert m["explain_concept"]["cache_hit_rate"] > 0 and m["explain_concept"]["cold_loads"] >= 1
    assert client.delete("/admin/tutor-cache", headers=ADMIN).json()["deleted"] >= 1


def test_a_wrong_answer_does_not_move_mission_progress(client):
    """Progress counts right answers only: a wrong answer leaves items_correct at 0, a right one makes it 1."""
    from app.engines import catalog
    a = client.post("/auth/register", json={"email": "wrong.answer@example.com", "password": "a-long-password"}).json()
    h = {"Authorization": f"Bearer {a['token']}"}
    item = next(i for i in catalog().items.values() if i["kind"] == "single" and i["scored"])
    right = item["reveal"]["answer"]  # an option index
    wrong = 1 if right == 0 else 0
    node = item["node"]
    status = lambda: next(s for s in client.get("/skills", headers=h).json() if s["id"] == node)["status"]  # noqa: E731
    client.post(f"/tasks/{item['id']}/attempts", headers=h, json={"response": wrong, "confidence": 3})
    st = status()
    assert st["items_answered"] == 1 and st["items_correct"] == 0 and not st["done"]
    client.post(f"/tasks/{item['id']}/attempts", headers=h, json={"response": right, "confidence": 3})
    assert status()["items_correct"] == 1


def test_tutor_masks_personal_data_before_the_model_and_caches_first_chat_questions(client, monkeypatch):
    from app import tutor_api
    seen = []
    monkeypatch.setattr(tutor_api, "TUTOR_ENABLED", True)
    monkeypatch.setattr(tutor_api.tutor_pipeline, "handles", lambda mode: False)
    monkeypatch.setattr(tutor_api, "call_model", lambda m: (seen.append(m), ({"text": "Fine. What next?", "mermaid": None}, 10, 1, 1))[1])
    h = {"Authorization": f"Bearer {client.post('/auth/session', json={'display_name': 'mask'}).json()['token']}"}
    client.post("/tutor", headers=h, json={"message": "My email is jan.kowalski@example.com, PESEL 90010112345",
                                            "history": [{"role": "user", "text": "call me at +48 600 700 800"}]})
    sent = " ".join(m["content"] for m in seen[0])
    assert "jan.kowalski@example.com" not in sent and "90010112345" not in sent and "600 700 800" not in sent
    assert "[email]" in sent and "[pesel]" in sent
    q = {"mode": "explain_concept", "message": "What is a bond, in one line?"}  # tutor chat: no node, no history
    client.post("/tutor", headers=h, json=q)
    again = client.post("/tutor", headers=h, json=q).json()
    assert again.get("cached") is True and len(seen) == 2


def test_tutor_has_a_per_minute_limit_and_a_daily_budget(client, monkeypatch):
    from app import tutor_api
    monkeypatch.setattr(tutor_api, "TUTOR_ENABLED", True)
    monkeypatch.setattr(tutor_api.tutor_pipeline, "handles", lambda mode: False)
    monkeypatch.setattr(tutor_api, "call_model", lambda m: ({"text": "Ok. And?", "mermaid": None}, 10, 1, 1))
    monkeypatch.setattr(tutor_api, "TUTOR_PER_MINUTE", 3)
    h = {"Authorization": f"Bearer {client.post('/auth/session', json={'display_name': 'limit'}).json()['token']}"}
    codes = [client.post("/tutor", headers=h, json={"mode": "explain_result", "message": f"q{i}"}).status_code for i in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.post("/tutor", headers=h, json={"mode": "title", "message": "x"}).status_code == 200  # titles are free
    tutor_api._minute.clear()
    monkeypatch.setattr(tutor_api, "DAILY_BUDGET", 3)  # 3 calls already today
    r = client.post("/tutor", headers=h, json={"mode": "explain_result", "message": "one more"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "daily_budget"
    g = {"X-Guest-Id": "g-limit", "CF-Connecting-IP": "203.0.113.7"}  # guests are counted per visitor IP in memory
    tutor_api._minute.clear()
    tutor_api._guest_day.clear()
    assert [client.post("/tutor", headers=g, json={"mode": "explain_result", "message": f"g{i}"}).status_code for i in range(4)] == [200, 200, 200, 429]
    other = {"X-Guest-Id": "g-other", "CF-Connecting-IP": "203.0.113.8"}  # another visitor is not affected
    assert client.post("/tutor", headers=other, json={"mode": "explain_result", "message": "hi"}).status_code == 200
    tutor_api._minute.clear()
    tutor_api._guest_day.clear()


def test_flagged_tutor_answers_can_be_labelled(client, monkeypatch):
    from app import tutor_api
    monkeypatch.setattr(tutor_api, "TUTOR_ENABLED", True)
    monkeypatch.setattr(tutor_api.tutor_pipeline, "handles", lambda mode: False)
    monkeypatch.setattr(tutor_api, "call_model", lambda m: ({"text": "Buy Nvidia now.", "mermaid": None}, 10, 1, 1))
    h = {"Authorization": f"Bearer {client.post('/auth/session', json={'display_name': 'label'}).json()['token']}"}
    client.post("/tutor", headers=h, json={"mode": "explain_result", "message": "Which stock should I buy?"})
    A = {"X-Admin-Key": "test-admin-key"}
    ev = client.get("/admin/llm-events?flagged=true&limit=1", headers=A).json()["items"][0]
    assert ev["review_label"] is None
    r = client.patch(f"/admin/llm-events/{ev['id']}", headers=A, json={"label": "advice"}).json()
    assert r["review_label"] == "advice" and r["reviewed_at"]
    assert client.get("/admin/llm-events?flagged=true&limit=1", headers=A).json()["items"][0]["review_label"] == "advice"
    assert client.patch(f"/admin/llm-events/{ev['id']}", headers=A, json={"label": "nonsense"}).status_code == 400
    assert client.patch(f"/admin/llm-events/{ev['id']}", json={"label": "ok"}).status_code in (401, 403)
    assert client.patch("/admin/llm-events/999999", headers=A, json={"label": "ok"}).status_code == 404
