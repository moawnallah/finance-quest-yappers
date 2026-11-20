import datetime as dt

import pytest
import yaml

from tutor import kb
from tutor.llm import LiteLLMClient, RoleRefused

TODAY = dt.date(2026, 11, 20)


def write_content(tmp_path, reviewer="Ann", licence="cc-by-4.0", valid_until=None, body="Short body."):
    (tmp_path / "nodes").mkdir()
    (tmp_path / "sources.yaml").write_text(yaml.safe_dump([{"id": "src", "url": "https://x.org", "licence": licence}]),
                                           encoding="utf-8")
    card = {"id": "s1.c1", "title": "Buffer", "body": body, "links": ["src"]}
    if valid_until:
        card["valid_until"] = valid_until
    for node, after in (("S1", ["F1"]), ("F1", [])):
        (tmp_path / "nodes" / f"{node}.yaml").write_text(
            yaml.safe_dump({"node": node, "after": after, "reviewer": reviewer,
                            "cards": [{**card, "id": f"{node.lower()}.c1"}]}), encoding="utf-8")
    return tmp_path


def test_ingest_accepts_a_reviewed_licensed_card(tmp_path):
    accepted, rejected = kb.ingest(write_content(tmp_path), TODAY)
    assert {p["chunk_id"] for p in accepted} == {"s1.c1", "f1.c1"} and not rejected


@pytest.mark.parametrize("kw, problem", [
    ({"reviewer": None}, "not reviewed"),
    ({"licence": "to_check"}, "licence of src not checked"),
    ({"valid_until": "2026-01-01"}, "expired"),
    ({"body": "word " * 151}, "longer than 150 words"),
])
def test_ingest_rejects_unsafe_passages(tmp_path, kw, problem):
    # Unreviewed, unlicensed, expired or overlong text must never reach the model.
    accepted, rejected = kb.ingest(write_content(tmp_path, **kw), TODAY)
    assert not accepted and all(any(problem in e for e in errs) for errs in rejected.values())


def test_search_prefers_the_node_then_prerequisites():
    passages = [{"chunk_id": "f1", "node_ids": ["F1"], "body": "budget surplus months"},
                {"chunk_id": "s1", "node_ids": ["S1"], "body": "emergency fund months"},
                {"chunk_id": "p1", "node_ids": ["P1"], "body": "months months months"}]
    found = kb.search(passages, "S1", "how many months", 3, {"S1": ["F1"]})
    assert [p["chunk_id"] for p in found] == ["s1", "f1"]


def test_repo_cards_load_without_errors():
    # The real content must parse; while cards are drafts they are rejected only for review status.
    accepted, rejected = kb.ingest(today=TODAY)
    assert rejected and all(errs == ["not reviewed"] for errs in rejected.values()), rejected


CONFIG = {"roles": {
    "tutor_small": {"primary": {"model": "ollama/x"}, "allowed_for_user_data": True},
    "tutor_cloud": {"primary": {"model": "vertex_ai/y"}, "allowed_for_user_data": False, "cloud": True},
}}


def test_cloud_role_is_refused_for_user_data_before_any_call(monkeypatch):
    monkeypatch.setenv("CLOUD_ROLES_ENABLED", "true")
    with pytest.raises(RoleRefused):
        LiteLLMClient(CONFIG).complete("tutor_cloud", [], None, 10, contains_user_data=True)


def test_cloud_role_is_off_unless_enabled(monkeypatch):
    monkeypatch.delenv("CLOUD_ROLES_ENABLED", raising=False)
    with pytest.raises(RoleRefused):
        LiteLLMClient(CONFIG).complete("tutor_cloud", [], None, 10, contains_user_data=False)


def test_model_allowlist(monkeypatch):
    monkeypatch.setenv("MODEL_ALLOWLIST", "ollama/other")
    with pytest.raises(RoleRefused):
        LiteLLMClient(CONFIG).complete("tutor_small", [], None, 10, contains_user_data=True)
