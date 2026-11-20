import json

import pytest

from fakes import CORRECT_BOX, TRUTH, FakeProvider, ScriptedLLM
from tutor import TutorRequest, answer
from tutor.context import build_context


def ok_json(text="The fee is part of what you borrow [K1].", cited=("K1",), q="What does RRSO include?"):
    return json.dumps({"text": text, "cited": list(cited), "check_question": q})


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("TUTOR_ENABLED", "true")
    monkeypatch.setenv("PROMPT_VERSION", "tutor-v1")


def hint(**kw):
    return TutorRequest(mode="hint", user_id="u1", node="F4", task_id="f4.m1", hint_level=1, **kw)


def test_hint_context_never_contains_the_truth():
    # The structural guard: before submission the model's context has no truth value or weights.
    ctx = build_context(hint(), FakeProvider(submitted=True))
    dumped = json.dumps(ctx)
    assert str(TRUTH) not in dumped and "weight" not in dumped and "reveal" not in ctx["fields"]


def test_explain_result_needs_a_submitted_attempt_and_then_gets_the_reveal():
    req = TutorRequest(mode="explain_result", user_id="u1", node="F4", task_id="f4.m1", attempt_id="a1")
    with pytest.raises(ValueError):
        build_context(req, FakeProvider(submitted=False))
    assert build_context(req, FakeProvider(submitted=True))["fields"]["reveal"]["truth"] == TRUTH


def test_a_good_answer_passes_with_links():
    resp = answer(hint(), FakeProvider(), ScriptedLLM(ok_json()))
    assert not resp.fallback and resp.links == [{"label": "K1", "url": "https://example.org/rrso"}]
    assert resp.event["checks_failed"] == [] and resp.hint_paid is False


def test_third_hint_is_paid():
    # Hints 1-2 are free; the app lowers the score from hint 3 on, based on this flag.
    req = TutorRequest(mode="hint", user_id="u1", node="F4", task_id="f4.m1", hint_level=3)
    assert answer(req, FakeProvider(), ScriptedLLM(ok_json())).hint_paid is True


def test_answer_leak_falls_back_to_the_stored_explanation():
    leaked = ok_json(text=f"You will pay {TRUTH:,} PLN; {CORRECT_BOX.lower()} [K1].")
    resp = answer(hint(), FakeProvider(), ScriptedLLM(leaked))
    assert resp.fallback and resp.text == "stored explanation for f4.m1"
    assert resp.event["flagged_for_review"] and any("leaks" in c for c in resp.checks_failed)


def test_invalid_json_is_retried_once_then_falls_back():
    llm = ScriptedLLM("not json", "still not json")
    resp = answer(hint(), FakeProvider(), llm)
    assert resp.fallback and len(llm.calls) == 2 and resp.checks_failed == ["invalid json"]


def test_advice_request_never_reaches_the_model():
    llm = ScriptedLLM()  # would raise IndexError if called
    resp = answer(TutorRequest(mode="explain_concept", user_id="u1", node="I5", message="Which fund should I buy?"),
                  FakeProvider(), llm)
    assert resp.intent == "advice_request" and not llm.calls and resp.event["flagged_for_review"]


def test_personal_data_is_masked_before_the_model():
    llm = ScriptedLLM(ok_json())
    answer(hint(message="my email is jan.kowalski@example.com and PESEL 90010112345"), FakeProvider(), llm)
    sent = json.dumps(llm.calls[0]["messages"])
    assert "jan.kowalski" not in sent and "90010112345" not in sent


def test_kill_switch_skips_the_model(monkeypatch):
    monkeypatch.setenv("TUTOR_ENABLED", "false")
    llm = ScriptedLLM()
    resp = answer(hint(), FakeProvider(), llm)
    assert resp.fallback and not llm.calls


def test_model_error_falls_back():
    class Broken:
        def complete(self, *a, **k):
            raise TimeoutError

    resp = answer(hint(), FakeProvider(), Broken())
    assert resp.fallback and resp.checks_failed == ["model: TimeoutError"]
