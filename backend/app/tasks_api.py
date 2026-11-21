"""Skills-tree endpoints backed by the task engines (docs/task_engines.md): easy items and medium tasks.

They sit beside the older wheel endpoints (/wheel, /nodes, /answers), which serve content/roadmap.json.
Answers, truth values and box weights never leave this module before a submission."""
import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from hard import text as hard_text
from hard.dsl import check as hard_check
from app import scales
from app import schemas as s
from app.db import get_db
from app.deps import ApiError, current_user, log_event
from app.engines import AttemptError, Catalog, catalog, easy, hard, localize, medium, node_status
from app.models import Attempt, User

router = APIRouter(tags=["skills"])


def _node(cat: Catalog, node_id: str) -> dict:
    if node_id not in cat.nodes:
        raise ApiError(404, "not_found", f"No skill node '{node_id}'")
    return cat.nodes[node_id]


def _attempts(db: Session, user_id: str, node_id: str) -> list[Attempt]:
    return list(db.scalars(select(Attempt).where(Attempt.user_id == user_id, Attempt.node_id == node_id)
                           .order_by(Attempt.id)))


def _status(db: Session, cat: Catalog, user_id: str, node_id: str) -> dict:
    return node_status(cat, node_id, user_id, _attempts(db, user_id, node_id))


@router.get("/skills", response_model=list[s.SkillSummary])
def list_skills(lang: str = "en", user: User = Depends(current_user), db: Session = Depends(get_db)):
    """All skills-tree nodes that have engine content, with this user's completion."""
    cat = catalog()
    return [s.SkillSummary(id=n["node"], title=localize(n["title"], lang), panel=n["panel"], after=n["after"],
                           live=n["live"], cards=len(n["cards"]), items=len(n["items"]),
                           medium_tasks=len(cat.tasks_by_node.get(n["node"], [])),
                           status=_status(db, cat, user.id, n["node"]))
            for n in sorted(cat.nodes.values(), key=lambda n: (n["panel"], n["node"]))]


@router.get("/skills/{node_id}", response_model=s.SkillDetail)
def skill_detail(node_id: str, lang: str = "en", user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cards, easy items and medium tasks of one node, without answers."""
    cat = catalog()
    node = _node(cat, node_id)
    log_event(db, user, "skill_opened", node_id=node_id)
    db.commit()
    return s.SkillDetail(node=easy.node_view(node, lang),
                         medium=[medium.question_view(t, lang) for t in cat.tasks_by_node.get(node_id, [])],
                         hard=[hard.question_view(t, lang) for t in cat.hard_by_node.get(node_id, [])],
                         status=_status(db, cat, user.id, node_id))


def _drawn(node_id: str, context: str, lang: str, user: User) -> s.DrawnTestOut:
    cat = catalog()
    _node(cat, node_id)
    draw = easy.prerequisite_test if context == "prerequisite" else easy.test_out
    ids = draw(cat.nodes, node_id, seed=user.id)
    return s.DrawnTestOut(node=node_id, context=context,
                          items=[easy.question_view(cat.items[i], lang) for i in ids])


@router.get("/skills/{node_id}/prerequisite-test", response_model=s.DrawnTestOut)
def prerequisite_test(node_id: str, lang: str = "en", user: User = Depends(current_user)):
    """2-3 check items from the node's prerequisite nodes. Passing all marks the node's easy part done."""
    return _drawn(node_id, "prerequisite", lang, user)


@router.get("/skills/{node_id}/test-out", response_model=s.DrawnTestOut)
def test_out(node_id: str, lang: str = "en", user: User = Depends(current_user)):
    """2 of the node's own check items, for nodes the onboarding router marks 'probably known'."""
    return _drawn(node_id, "test_out", lang, user)


@router.get("/tasks/{task_id}", response_model=s.TaskOut)
def get_task(task_id: str, lang: str = "en", user: User = Depends(current_user)):
    """One easy item or medium task, without answers, truth or weights."""
    found = catalog().find(task_id)
    if not found:
        raise ApiError(404, "not_found", f"No task '{task_id}'")
    level, rec = found
    view = {"easy": easy.question_view, "medium": medium.question_view, "hard": hard.question_view}[level](rec, lang)
    if level == "hard":
        view["code"] = _code_panel(rec)
    return s.TaskOut(level=level, task=view)


STARTER = '''# Your plan runs once every month. Write rules with if / elif / else,
# indent the lines under a rule by 4 spaces, then press "Run tests".
# Example:
# if buffer_months < 2:
#     save_to_buffer(cash)
'''


def _hard_lists(rec: dict) -> tuple[list[str], list[str]]:
    q = rec["question"]
    return [v["name"] for v in q["vars"]], [a["name"] for a in q.get("assets") or []]


def _code_panel(rec: dict) -> dict:
    """What the app's hard-task code panel needs: starter code, the public tests, and the vocabulary."""
    from hard.dsl import BLOCKS, VARS
    q = rec["question"]
    names, assets = _hard_lists(rec)
    starter = hard_text.to_text(q.get("starter_program")) or STARTER  # an empty starter program gets the guide
    actions = []
    for b in [p["block"] for p in q["palette"]]:
        if b in ("save_to_buffer", "save_to_pot", "pay_debt", "invest", "sell_investments"):
            actions.append({"code": f"{b}(amount)", "meaning": BLOCKS[b]["text"].replace("{amount}", "amount")})
        elif b in ("invest_in", "sell"):
            actions.append({"code": f"{b}(amount, asset)", "meaning": BLOCKS[b]["text"].replace("{amount}", "amount").replace("{asset}", "asset")})
        elif b == "rebalance":
            actions.append({"code": "rebalance()", "meaning": BLOCKS[b]["text"]})
    return {"starter": starter, "public_tests": hard.public_tests(rec["meta"]),
            "hidden_tests": max(0, len(rec["meta"]["optional"]) - hard.PUBLIC_OPTIONAL),
            "values": [{"name": n, "meaning": VARS.get(n, n)} for n in names], "assets": assets, "actions": actions,
            "own_variables": "my_total = 0, my_total += cash (up to 3 names)" if "set_var" in [p["block"] for p in q["palette"]] else None}


def _program_from(rec: dict, response):
    """A hard-task response: {"code": "..."} text from the code panel, or the program / Blockly JSON."""
    if isinstance(response, dict) and isinstance(response.get("code"), str):
        names, assets = _hard_lists(rec)
        try:
            return hard_text.to_program(response["code"], names, assets)
        except hard_text.TextError as e:
            raise ApiError(400, "invalid_response", str(e)) from e
    return response


@router.post("/tasks/{task_id}/run")
def run_public_tests(task_id: str, body: s.CodeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Hard tasks: run the public tests on code from the code panel. Nothing is scored or stored as an
    attempt, and hidden tests are not run: submit (POST /tasks/{id}/attempts with {"code": ...}) for that."""
    found = catalog().find(task_id)
    if not found or found[0] != "hard":
        raise ApiError(404, "not_found", f"No hard task '{task_id}'")
    rec = found[1]
    program = _program_from(rec, {"code": body.code})
    q = rec["question"]
    names, assets = _hard_lists(rec)
    errors = hard_check(program, [b["block"] for b in q["palette"]], names, q["limits"].get("max_blocks", 30),
                        q["limits"].get("max_depth", 5), assets)
    if errors:
        raise ApiError(400, "invalid_response", "; ".join(errors))
    started = time.perf_counter()
    out = hard.run_public(rec["meta"], program)
    log_event(db, user, "hard_tests_run", task_id=task_id, required_passed=out["required_passed"])
    db.commit()
    return {**out, "duration_ms": int((time.perf_counter() - started) * 1000)}


@router.post("/tasks/{task_id}/attempts", response_model=s.AttemptOut)
def submit_attempt(task_id: str, body: s.AttemptIn, lang: str = "en",
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Score one answer, store the attempt record, and return the reveal and the node's completion."""
    cat = catalog()
    found = cat.find(task_id)
    if not found:
        raise ApiError(404, "not_found", f"No task '{task_id}'")
    level, rec = found

    node_id = rec["node"]
    if body.context != "practice":
        if level != "easy" or not body.for_node:
            raise ApiError(400, "invalid_context", f"'{body.context}' needs an easy item and 'for_node'")
        _node(cat, body.for_node)
        draw = easy.prerequisite_test if body.context == "prerequisite" else easy.test_out
        if task_id not in draw(cat.nodes, body.for_node, seed=user.id):
            raise ApiError(400, "invalid_context", f"'{task_id}' is not in your {body.context} for {body.for_node}")
        node_id = body.for_node
    elif level in ("easy", "hard") and body.reasons:
        raise ApiError(400, "invalid_response", "reasons are only for medium tasks")

    started = time.perf_counter()
    try:
        if level == "easy":
            result, reveal = easy.score(rec, body.response, body.confidence), easy.reveal_view(rec, lang)
        elif level == "medium":
            result = medium.score(rec, body.response, body.reasons or [], body.confidence)
            reveal = medium.reveal_view(rec, lang)
        else:
            body.response = _program_from(rec, body.response)
            if not isinstance(body.response, dict):
                raise AttemptError("a hard task needs the Blockly workspace JSON or the program JSON")
            result = hard.score(rec, body.response)
            result.update(confidence=body.confidence, p=None if body.confidence is None else (body.confidence - 1) / 4,
                          score_estimate=None, score_reasons=None)
            reveal = {**hard.reveal_view(rec, lang),
                      "result": {k: result.get(k) for k in ("obligatory", "optional", "story", "futures")}}
    except AttemptError as e:
        raise ApiError(400, "invalid_response", str(e)) from e
    duration_ms = int((time.perf_counter() - started) * 1000)
    failed = next((t["name"] for t in result.get("obligatory") or [] if not t["passed"]), None)

    was_done = _status(db, cat, user.id, node_id)["done"]
    attempt = Attempt(user_id=user.id, task_id=task_id, node_id=node_id, level=level,
                      context=body.context, content_version=result["content_version"], response=result["response"],
                      confidence=result["confidence"], p=result["p"], score_estimate=result["score_estimate"],
                      score_reasons=result["score_reasons"], score=result["score"], started_at=body.started_at,
                      hints_used=body.hints_used, tutor_opened=body.tutor_opened, clarity_rating=body.clarity_rating,
                      accepted=result.get("accepted"), points=result.get("points"),
                      growth_index=result.get("growth_index"), failed_test=failed, duration_ms=duration_ms)
    db.add(attempt)
    db.flush()
    log_event(db, user, "attempt_submitted", task_id=task_id, level=level, context=body.context, score=result["score"])

    status = _status(db, cat, user.id, node_id)
    completed = status["done"] and not was_done
    if completed:
        log_event(db, user, "skill_completed", node_id=node_id)
    if result["score"] is not None and result["score"] >= 1:
        scales.award(db, user.id, "correct", task_id)
    if completed:
        scales.award(db, user.id, "mission", node_id)
    scales_total = scales.total(db, user.id)
    db.commit()
    return s.AttemptOut(attempt_id=attempt.id, task_id=task_id, level=level, score=result["score"],
                        score_estimate=result["score_estimate"], score_reasons=result["score_reasons"],
                        confidence=result["confidence"], p=result["p"], reveal=reveal, status=status,
                        node_completed=completed, accepted=result.get("accepted"), points=result.get("points"),
                        growth_index=result.get("growth_index"), scales_total=scales_total)
