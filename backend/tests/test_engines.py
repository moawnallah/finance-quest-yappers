"""Skills endpoints backed by the task engines: views hide answers, attempts are scored and stored,
and node completion follows docs/task_engines.md."""
import json
from pathlib import Path

import pytest

OUTPUT = Path(__file__).resolve().parent.parent / "data" / "output"
NODES = {n["node"]: n for n in json.loads((OUTPUT / "easy.json").read_text())["nodes"]}
ITEMS = {i["id"]: i for n in NODES.values() for i in n["items"]}
TASKS = {t["id"]: t for t in json.loads((OUTPUT / "medium_tasks.json").read_text())["tasks"]}
SECRET_KEYS = {"answer", "why", "feedback", "weight", "explain", "truth", "outcome"}


def _right(item_id):
    return ITEMS[item_id]["reveal"]["answer"]


def _wrong(item_id):
    item = ITEMS[item_id]
    answer = item["reveal"]["answer"]
    if item["kind"] == "true_false":
        return not answer
    if item["kind"] == "numeric":
        return answer * 10 + 1000
    if item["kind"] == "multi":
        return [i for i in range(len(item["question"]["options"])) if i not in answer][:1] or [0]
    return (answer + 1) % len(item["question"]["options"])


def _best_reasons(task_id):
    task = TASKS[task_id]
    k = task["question"]["reasons"]["pick"]["min"]
    ranked = sorted(task["reveal"]["reasons"], key=lambda b: -b["weight"])
    return [b["id"] for b in ranked[:k]]


def _keys(obj):
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


@pytest.fixture(scope="module")
def learner(client):
    token = client.post("/auth/session", json={"display_name": "Ola"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _submit(client, h, task_id, **body):
    body.setdefault("confidence", 4)
    return client.post(f"/tasks/{task_id}/attempts", headers=h, json=body)


def test_skills_list(client, learner):
    skills = {s["id"]: s for s in client.get("/skills", headers=learner).json()}
    assert set(skills) == set(NODES)
    assert skills["D1"]["medium_tasks"] == 1 and skills["I4"]["medium_tasks"] == 0
    assert skills["I4"]["status"]["done"] is False and skills["I4"]["status"]["items_answered"] == 0


def test_views_hide_answers(client, learner):
    detail = client.get("/skills/D1", headers=learner).json()
    assert detail["node"]["node"] == "D1" and detail["medium"][0]["id"] == "d1.m1"
    assert not _keys(detail["node"]["items"]) & SECRET_KEYS
    assert not _keys(detail["medium"]) & SECRET_KEYS
    task = client.get("/tasks/d1.m1", headers=learner).json()
    assert task["level"] == "medium" and not _keys(task["task"]) & SECRET_KEYS
    assert client.get("/tasks/i4.e1", headers=learner).json()["level"] == "easy"
    assert client.get("/tasks/nope", headers=learner).status_code == 404
    assert client.get("/skills/Z9", headers=learner).status_code == 404


def test_easy_attempt_scored_and_revealed(client, learner):
    r = _submit(client, learner, "i4.e1", response=_wrong("i4.e1")).json()
    assert r["score"] == 0 and r["level"] == "easy" and r["p"] == 0.75
    assert r["reveal"]["answer"] == _right("i4.e1") and r["reveal"]["why"]
    r = _submit(client, learner, "i4.e1", response=_right("i4.e1")).json()
    assert r["score"] == 1 and r["status"]["items_answered"] == 1


def test_invalid_attempts(client, learner):
    assert _submit(client, learner, "i4.e1", response=99).json()["error"]["code"] == "invalid_response"
    assert _submit(client, learner, "i4.e1", response=0, reasons=["x"]).status_code == 400
    assert _submit(client, learner, "d1.m1", response="down", reasons=["nope"]).status_code == 400
    assert _submit(client, learner, "i4.e1", response=0, confidence=7).status_code == 422
    assert _submit(client, learner, "i4.e1", response=0, context="prerequisite").status_code == 400  # no for_node


def test_node_completion_needs_easy_and_medium(client, learner):
    scored = [i["id"] for i in NODES["D1"]["items"] if i["scored"]]
    for item_id in scored:
        r = _submit(client, learner, item_id, response=_right(item_id)).json()
    assert r["status"]["easy_done"] and not r["status"]["done"] and not r["node_completed"]

    r = _submit(client, learner, "d1.m1", response="up", reasons=_best_reasons("d1.m1")).json()
    assert r["score"] == 1 and r["score_estimate"] is None  # day X: reasons only
    assert r["reveal"]["outcome"]["direction"] == "down"
    assert r["status"]["done"] and r["node_completed"]
    again = _submit(client, learner, "d1.m1", response="up", reasons=_best_reasons("d1.m1")).json()
    assert again["node_completed"] is False  # completed only once


def test_node_without_medium_done_by_easy_part(client, learner):
    for item_id in [i["id"] for i in NODES["I4"]["items"] if i["scored"]]:
        r = _submit(client, learner, item_id, response=_right(item_id)).json()
    assert r["status"]["done"] and r["status"]["item_average"] == 1


def test_prerequisite_test_flow(client, learner):
    drawn = client.get("/skills/P1/prerequisite-test", headers=learner).json()
    ids = [i["id"] for i in drawn["items"]]
    assert 2 <= len(ids) <= 3 and not _keys(drawn["items"]) & SECRET_KEYS
    assert [i["id"] for i in client.get("/skills/P1/prerequisite-test", headers=learner).json()["items"]] == ids
    outsider = next(i for i in ITEMS if i not in ids and ITEMS[i]["scored"])
    assert _submit(client, learner, outsider, response=_right(outsider), context="prerequisite",
                   for_node="P1").json()["error"]["code"] == "invalid_context"
    for item_id in ids:
        r = _submit(client, learner, item_id, response=_right(item_id), context="prerequisite", for_node="P1").json()
    assert r["status"]["node"] == "P1" and r["status"]["prerequisite"]["passed"] and r["status"]["easy_done"]


def test_test_out_flow(client, learner):
    ids = [i["id"] for i in client.get("/skills/S1/test-out", headers=learner).json()["items"]]
    assert len(ids) == 2
    for item_id in ids:
        r = _submit(client, learner, item_id, response=_right(item_id), context="test_out", for_node="S1").json()
    assert r["status"]["test_out"]["passed"] and r["status"]["done"]  # S1 has no medium task
