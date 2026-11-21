"""Our tutor pipeline behind POST /tutor and /tutor/stream (app/tutor_pipeline.py). The model call is
replaced by a fake that records what the model would have seen; each test checks one promise."""
import json

import pytest

ADMIN = {"X-Admin-Key": "test-admin-key"}
GOOD = {"text": "An index spreads the risk over many companies [K1].", "cited": ["K1"],
        "check_question": "Why does spreading the risk help?"}


def _item(item_id: str) -> dict:
    from app.engines import catalog  # app modules are imported after the client fixture set the test database
    return catalog().items[item_id]


@pytest.fixture()
def model(client, monkeypatch):
    """Turns the pipeline on and records every model call."""
    from app import tutor_api
    monkeypatch.setenv("TUTOR_PIPELINE", "true")
    calls, replies = [], []

    def fake(messages):
        calls.append(messages)
        return (replies.pop(0) if replies else GOOD), 5, 10, 5

    monkeypatch.setattr(tutor_api, "call_model", fake)
    return calls, replies


@pytest.fixture()
def user(client):
    token = client.post("/auth/session", json={"display_name": "Tutee"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _seen(calls) -> str:
    """What the model was sent apart from the fixed system prompt: context, history, the learner's message."""
    return "\n".join(m["content"] for messages in calls for m in messages if m["role"] != "system")


def _last_event(client) -> dict:
    return client.get("/admin/llm-events", params={"limit": 1}, headers=ADMIN).json()["items"][0]


@pytest.mark.parametrize("mode", ["hint", "explain_result"])
def test_before_answering_the_model_never_sees_the_answer(client, user, model, mode):
    # Neither a hint nor the app claiming "explain_result" may pull the answer before an attempt is stored.
    calls, _ = model
    r = client.post("/tutor", headers=user, json={"mode": mode, "message": "Can you help me?",
                                                   "context": {"node": "I4", "task_id": "i4.e1", "correct": "leaked by the app"}})
    why = _item("i4.e1")["reveal"]["why"]   # the options are on screen anyway; which one is right, and why, is not
    assert r.status_code == 200 and not r.json()["fallback"]
    assert all(s not in _seen(calls) for s in [why, "leaked by the app", '"reveal"', '"answer"'])
    assert _last_event(client)["mode"] == (mode if mode == "hint" else "explain_concept")


def test_a_hint_that_names_the_right_option_falls_back(client, user, model):
    # The leak check on the output: a small model may still blurt out the answer it can infer.
    _, replies = model
    from app.engines import easy
    right = easy.secrets(_item("i4.e1"))["strings"][0]
    replies.append({**GOOD, "text": f"Pick this one: {right} [K1]."})
    r = client.post("/tutor", headers=user, json={"mode": "hint", "message": "Which one?", "context": {"task_id": "i4.e1"}})
    assert r.json()["fallback"] is True and right not in r.json()["text"]
    assert any("leaks" in c for c in _last_event(client)["checks_failed"])


def test_after_answering_the_reveal_is_used(client, user, model):
    # The app opens the tutor after the answer; the server finds the attempt and gives the model the explanation.
    calls, _ = model
    item = _item("i4.e1")
    client.post("/tasks/i4.e1/attempts", headers=user, json={"response": item["reveal"]["answer"], "confidence": 3})
    r = client.post("/tutor", headers=user, json={"mode": "explain_concept", "message": "Why?", "context": {"task_id": "i4.e1"}})
    assert r.status_code == 200 and '"reveal"' in _seen(calls) and item["reveal"]["why"][:40] in _seen(calls)
    assert r.json()["text"].endswith(GOOD["check_question"]) and "[K1]" not in r.json()["text"]
    assert _last_event(client)["mode"] == "explain_result"


def test_advice_question_gets_the_template_without_a_model_call(client, user, model):
    calls, _ = model
    r = client.post("/tutor", headers=user, json={"mode": "explain_concept", "message": "Which ETF should I buy?"})
    assert calls == [] and r.json()["text"].startswith("I can't tell you which product to buy")
    assert _last_event(client)["intent"] == "advice_request"
    assert r.json()["template"] == "advice_request"
    assert _last_event(client)["model"] == "template"  # no model ran, so the event must not name one


def test_an_invented_number_falls_back_and_is_logged(client, user, model):
    # The number check is what stops a small model from making up returns; a failure must be visible in the admin panel.
    _, replies = model
    replies.append({**GOOD, "text": "An index returned 12.7% a year on average [K1]."})
    r = client.post("/tutor", headers=user, json={"mode": "explain_concept", "message": "Tell me about indexes",
                                                   "context": {"node": "I4"}})
    ev = _last_event(client)
    assert r.json()["fallback"] is True and ev["fallback_used"] and any("12.7" in c for c in ev["checks_failed"])


def test_stream_keeps_its_contract(client, user, model):
    # The app reads NDJSON lines from /tutor/stream; with the pipeline it gets one delta and the done line.
    r = client.post("/tutor/stream", headers=user, json={"mode": "explain_concept", "message": "What is an index?",
                                                          "context": {"node": "I4"}})
    lines = [json.loads(x) for x in r.text.splitlines() if x.strip()]
    assert [x["t"] for x in lines] == ["delta", "done"] and lines[0]["text"] == lines[1]["text"]


def test_with_the_flag_off_the_old_tutor_answers(client, user, monkeypatch):
    # Merge safety: until a test environment sets TUTOR_PIPELINE=true, /tutor behaves as before.
    from app import tutor_api
    monkeypatch.delenv("TUTOR_PIPELINE", raising=False)
    monkeypatch.setattr(tutor_api, "call_model", lambda messages: ({"text": "Old path.", "mermaid": None}, 5, 1, 1))
    r = client.post("/tutor", headers=user, json={"mode": "explain_concept", "message": "What is an index?"})
    assert r.json()["text"] == "Old path." and "check_question" not in r.json()
