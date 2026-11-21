"""Finance Quest API. Run: uvicorn app.main:app --reload  (docs at /docs, spec at /openapi.json)."""
import random
import secrets
import uuid
from statistics import mean
from typing import Literal

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from datetime import datetime, timezone

from app import scales
from app import auth, badges, progress
from app.catalog import CATALOG
from app.config import AB_VARIANTS, DATABASE_URL, ON_VERCEL
from app.db import get_db
from app.deps import ApiError, current_user, is_guest, log_event, require_admin, viewer
from app.models import (Answer, BenchmarkAnswer, BenchmarkQuestion, BenchmarkStat, Node, NodeProgress, Profile,
                        Question, Slice, User, UserBadge)
from app import schemas as s
from app.insights_api import router as insights_router
from app.tasks_api import router as skills_router
from app.admin import router as admin_router
from app.tutor_api import router as tutor_router

app = FastAPI(title="Finance Quest API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(skills_router)
app.include_router(admin_router)
app.include_router(tutor_router)
app.include_router(insights_router)

if ON_VERCEL and DATABASE_URL.startswith("sqlite:////tmp/"):
    # Serverless demo: a new instance starts with an empty /tmp, so build the schema and load the content.
    # Data is lost when the instance is recycled; the app then starts a fresh session.
    from app.db import Base, SessionLocal, engine
    from app.seed import seed

    Base.metadata.create_all(engine)
    with SessionLocal() as _db:
        seed(_db)


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def _error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "request_id": rid}})


@app.exception_handler(ApiError)
async def api_error(request: Request, exc: ApiError):
    return _error(request, exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    return _error(request, 422, "invalid_request", f"{'.'.join(map(str, first['loc']))}: {first['msg']}")


@app.get("/meta")
def meta():
    """Data catalogue: what each coded value means (risk levels, node states, question kinds, errors) and how to show it."""
    return CATALOG


@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "slices": db.scalar(select(func.count()).select_from(Slice))}


# ---------- auth and profile ----------

@app.post("/auth/session", response_model=s.SessionOut)
def create_session(body: s.SessionIn, db: Session = Depends(get_db)):
    user = User(id=str(uuid.uuid4()), token=secrets.token_urlsafe(32), display_name=body.display_name,
                variant=random.choice(AB_VARIANTS))
    db.add(user)
    db.flush()  # user row must exist before the event that references it
    log_event(db, user, "session_created")
    db.commit()
    return s.SessionOut(user_id=user.id, token=user.token, variant=user.variant)


@app.post("/auth/register", response_model=s.AccountOut, status_code=201)
def register(body: s.RegisterIn, request: Request, db: Session = Depends(get_db)):
    """Create an account. Every account starts fresh: guests are stateless and nothing carries over."""
    email = auth.normalize_email(body.email)
    if not auth.valid_email(email):
        raise ApiError(422, "invalid_email", "Enter a valid email address.")
    if db.scalar(select(User).where(User.email == email)):
        raise ApiError(409, "email_taken", "An account with this email already exists. Sign in instead.")
    user = None
    if user is None:  # every account starts fresh: guests are never stored, so nothing carries over
        user = User(id=str(uuid.uuid4()), token=secrets.token_urlsafe(32), variant=random.choice(AB_VARIANTS),
                    display_name=body.display_name or email.split("@")[0])
        db.add(user)
    user.email = email
    user.password_hash = auth.hash_password(body.password)
    user.is_admin = email in auth.ADMIN_EMAILS
    user.last_login_at = datetime.now(timezone.utc)
    if body.display_name:
        user.display_name = body.display_name
    db.flush()
    log_event(db, user, "account_created", admin=user.is_admin)
    db.commit()
    return s.AccountOut(user_id=user.id, token=user.token, variant=user.variant, email=user.email,
                        display_name=user.display_name, is_admin=user.is_admin)


@app.post("/auth/login", response_model=s.AccountOut)
def login(body: s.LoginIn, db: Session = Depends(get_db)):
    email = auth.normalize_email(body.email)
    if auth.too_many_failures(email):
        raise ApiError(429, "too_many_attempts", "Too many attempts. Wait a few minutes and try again.")
    user = db.scalar(select(User).where(User.email == email))
    if not user or not auth.verify_password(body.password, user.password_hash):
        auth.record_failure(email)
        raise ApiError(401, "wrong_credentials", "The email or password is wrong.")  # same message either way
    user.is_admin = email in auth.ADMIN_EMAILS  # follows ADMIN_EMAILS if it changes
    user.last_login_at = datetime.now(timezone.utc)
    log_event(db, user, "logged_in")
    db.commit()
    return s.AccountOut(user_id=user.id, token=user.token, variant=user.variant, email=user.email,
                        display_name=user.display_name, is_admin=user.is_admin)


@app.get("/me", response_model=s.AccountOut)
def me(user: User = Depends(current_user)):
    return s.AccountOut(user_id=user.id, token=user.token, variant=user.variant, email=user.email,
                        display_name=user.display_name, is_admin=user.is_admin)


@app.post("/me/profile")
def save_profile(body: s.ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    prof = db.get(Profile, user.id) or Profile(user_id=user.id)
    prof.age_group, prof.goal, prof.experience = body.age_group, body.goal, body.experience
    prof.confidence_before = body.confidence_before
    db.add(prof)
    log_event(db, user, "profile_saved", **body.model_dump())
    db.commit()
    return {"ok": True}


@app.post("/me/confidence")
def save_confidence(body: s.ConfidenceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    prof = db.get(Profile, user.id)
    if not prof:
        raise ApiError(409, "no_profile", "Save the profile first")
    prof.confidence_after = body.value
    log_event(db, user, "confidence_after", value=body.value)
    db.commit()
    return {"ok": True}


# ---------- wheel, tree, node ----------

START_FOR_GOAL = {"habit": {"stocks", "mutual_and_index_funds"}, "kids": {"stocks", "bonds"},
                  "retire": {"bonds", "guaranteed_products", "money_market"}}


@app.get("/wheel", response_model=s.WheelOut)
def wheel(user: User = Depends(current_user), db: Session = Depends(get_db)):
    prof = db.get(Profile, user.id)
    highlight = START_FOR_GOAL.get(prof.goal, set()) if prof else set()
    slices = db.scalars(select(Slice).order_by(Slice.position)).all()
    return s.WheelOut(slices=[s.SliceOut(key=x.key, label=x.label, risk=x.risk, start=x.start,
                                         progress=progress.slice_progress(db, user.id, x),
                                         highlight=x.key in highlight) for x in slices])


@app.get("/wheel/{slice_key}/tree", response_model=s.TreeOut)
def tree(slice_key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sl = db.get(Slice, slice_key)
    if not sl:
        raise ApiError(404, "not_found", f"No slice '{slice_key}'")
    return s.TreeOut(slice=sl.key, label=sl.label, nodes=[s.NodeOut(**n) for n in progress.node_states(db, user.id, sl)])


@app.get("/nodes/{node_id}", response_model=s.NodeDetailOut)
def node_detail(node_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if not node or node.retired:
        raise ApiError(404, "not_found", f"No node '{node_id}'")
    state = next(n["state"] for n in progress.node_states(db, user.id, node.slice) if n["id"] == node.id)
    qs = [s.QuestionOut(id=q.id, kind=q.kind, q=q.text, options=q.options) for q in node.questions if not q.retired]
    log_event(db, user, "node_opened", node_id=node.id)
    db.commit()
    return s.NodeDetailOut(id=node.id, title=node.title, slice=node.slice_key, state=state, questions=qs)


@app.post("/answers", response_model=s.AnswerOut)
def answer(body: s.AnswerIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.get(Question, body.question_id)
    if not q or q.retired:
        raise ApiError(404, "not_found", f"No question '{body.question_id}'")
    if body.choice >= len(q.options):
        raise ApiError(422, "invalid_choice", "choice is out of range")

    is_correct = (body.choice == q.answer) if q.kind == "objective" else None
    prior = db.scalar(select(func.count()).select_from(Answer).where(
        Answer.user_id == user.id, Answer.question_id == q.id,
        *([Answer.is_correct.is_(True)] if q.kind == "objective" else [])))
    db.add(Answer(user_id=user.id, question_id=q.id, choice=body.choice, is_correct=is_correct))
    db.flush()
    xp = progress.xp_for(q, is_correct, first_time=not prior)
    completed, unlocked = progress.maybe_complete_node(db, user.id, q.node)
    log_event(db, user, "answer_submitted", question_id=q.id, kind=q.kind, choice=body.choice, is_correct=is_correct)
    if completed:
        log_event(db, user, "node_completed", node_id=q.node_id)
    db.flush()
    new_badges = badges.evaluate(db, user.id)
    for b in new_badges:
        log_event(db, user, "badge_awarded", badge=b["key"])
    db.commit()
    return s.AnswerOut(kind=q.kind, is_correct=is_correct,
                       correct_choice=q.answer if q.kind == "objective" else None,
                       explanation=q.why if q.kind == "objective" else None,
                       feedback=q.feedback[body.choice] if q.kind == "behaviour" and q.feedback else None,
                       sources=[x.url for x in q.sources], xp_awarded=xp,
                       node_completed=completed, unlocked=unlocked, new_badges=new_badges)


# ---------- EU benchmark (before / after) ----------

@app.get("/benchmark", response_model=list[s.BenchmarkQuestionOut])
def benchmark(stage: str = "before", user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for q in db.scalars(select(BenchmarkQuestion).order_by(BenchmarkQuestion.position)):
        opts = [{"choice": i, "text": t} for i, t in enumerate(q.options)]
        random.Random(f"{user.id}:{stage}:{q.id}").shuffle(opts)  # stable per user and stage
        out.append(s.BenchmarkQuestionOut(id=q.id, topic=q.topic, q=q.text, options=opts))
    return out


def _band(score: int) -> str:
    return "high" if score >= 4 else "medium" if score >= 2 else "low"


@app.post("/benchmark/answers", response_model=s.BenchmarkResultOut)
def benchmark_answers(body: s.BenchmarkSubmitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    questions = {q.id: q for q in db.scalars(select(BenchmarkQuestion))}
    if {a.question_id for a in body.answers} != set(questions):
        raise ApiError(422, "incomplete", f"Answer all {len(questions)} benchmark questions once")
    if db.scalar(select(func.count()).select_from(BenchmarkAnswer).where(
            BenchmarkAnswer.user_id == user.id, BenchmarkAnswer.stage == body.stage)):
        raise ApiError(409, "already_submitted", f"The '{body.stage}' benchmark was already submitted")
    per_q, score = [], 0
    for a in body.answers:
        q = questions[a.question_id]
        ok = a.choice == q.answer
        score += ok
        db.add(BenchmarkAnswer(user_id=user.id, stage=body.stage, question_id=q.id, choice=a.choice, is_correct=ok))
        per_q.append({"question_id": q.id, "topic": q.topic, "is_correct": ok, "why": q.why,
                      "correct_pl": q.correct_pl, "correct_eu": q.correct_eu})
    band = _band(score)
    stat = db.get(BenchmarkStat, "score_high_4_or_5_correct")
    comparison = (f"You got {score} of {len(questions)}. In the EU's Eurobarometer survey, {stat.pl}% of Poles "
                  f"and {stat.eu}% of EU adults answered 4 or 5 correctly.") if stat else f"You got {score} of {len(questions)}."
    log_event(db, user, "benchmark_submitted", stage=body.stage, score=score)
    db.flush()
    new_badges = badges.evaluate(db, user.id)
    for b in new_badges:
        log_event(db, user, "badge_awarded", badge=b["key"])
    db.commit()
    return s.BenchmarkResultOut(stage=body.stage, score=score, out_of=len(questions), band=band,
                                comparison=comparison, per_question=per_q, new_badges=new_badges)


# ---------- progress, practice, results ----------

def _benchmark_score(db: Session, user_id: str, stage: str) -> int | None:
    rows = db.scalars(select(BenchmarkAnswer.is_correct).where(
        BenchmarkAnswer.user_id == user_id, BenchmarkAnswer.stage == stage)).all()
    return sum(rows) if rows else None


@app.get("/me/progress", response_model=s.ProgressOut)
def my_progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return s.ProgressOut(
        xp=progress.total_xp(db, user.id), streak_days=progress.streak_days(db, user.id),
        nodes_completed=db.scalar(select(func.count()).select_from(NodeProgress).where(NodeProgress.user_id == user.id)),
        nodes_total=db.scalar(select(func.count()).select_from(Node).where(Node.retired.is_(False))),
        benchmark_before=_benchmark_score(db, user.id, "before"),
        benchmark_after=_benchmark_score(db, user.id, "after"))


@app.get("/me/badges", response_model=list[s.MyBadgeOut])
def my_badges(user: User = Depends(current_user), db: Session = Depends(get_db)):
    got = {b.badge_key: b.awarded_at for b in db.scalars(select(UserBadge).where(UserBadge.user_id == user.id))}
    return [s.MyBadgeOut(**badges.public(k), earned=k in got, awarded_at=got[k].isoformat() if k in got else None)
            for k in badges.BADGES]


class ScaleAwardIn(BaseModel):
    source: Literal["daily_right", "daily_tried", "quick_check"] = Field(
        description="daily_right / daily_tried: today's daily scenario (once a day); quick_check: the placement check (once).")


@app.get("/me/scales")
def my_scales(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The learner's Scales (kept on the server) and level."""
    n = scales.total(db, user.id)
    return {"scales": n, "level": scales.level_of(n)}


@app.post("/me/scales")
def award_scales(body: ScaleAwardIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Rewards earned outside a task: the daily scenario and the quick check. Correct answers and finished
    missions are awarded by POST /tasks/{id}/attempts."""
    ref = "once" if body.source == "quick_check" else datetime.now(timezone.utc).date().isoformat()
    added = scales.award(db, user.id, body.source, ref)
    db.commit()
    n = scales.total(db, user.id)
    return {"awarded": added, "scales": n, "level": scales.level_of(n)}


@app.get("/leagues")
def leagues(user=Depends(viewer), db: Session = Depends(get_db), x_guest_scales: int | None = Header(default=None)):
    """Real leagues: learners grouped by level (Beginner 0-299, Intermediate 300-999, Expert 1000+ Scales),
    ranked by Scales. Admin accounts are left out."""
    if is_guest(user):
        return scales.leagues(db, user, me_total=max(0, x_guest_scales or 0))
    return scales.leagues(db, user)


LEAGUE_SIZE = 10


@app.get("/leaderboard", response_model=s.LeaderboardOut)
def leaderboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Small weekly leagues: users are grouped in sign-up order into leagues of 10, ranked by XP earned this week."""
    # Weekly leagues of 10 registered learners (guests are not ranked; a guest sees their own row).
    ids = list(db.scalars(select(User.id).where(User.email.is_not(None)).order_by(User.created_at, User.id)))
    if user.id not in ids:
        ids.append(user.id)
    league = ids.index(user.id) // LEAGUE_SIZE
    members = db.scalars(select(User).where(User.id.in_(ids[league * LEAGUE_SIZE:(league + 1) * LEAGUE_SIZE]))).all()
    since = progress.week_start()
    rows = sorted(((progress.total_xp(db, m.id, since), m) for m in members), key=lambda t: (-t[0], t[1].display_name))
    return s.LeaderboardOut(league=league + 1, week_start=since.isoformat(), entries=[
        s.LeaderboardEntry(rank=i + 1, display_name=m.display_name, weekly_xp=xp, is_me=m.id == user.id)
        for i, (xp, m) in enumerate(rows)])


@app.get("/admin/ab-results", dependencies=[Depends(require_admin)])
def ab_results(db: Session = Depends(get_db)):
    """Per A/B variant: users, benchmark before/after, confidence before/after, share choosing 'hold'."""
    out = {}
    for v in AB_VARIANTS:
        users = db.scalars(select(User).where(User.variant == v)).all()
        ids = [u.id for u in users]
        before = [x for x in (_benchmark_score(db, i, "before") for i in ids) if x is not None]
        after = [x for x in (_benchmark_score(db, i, "after") for i in ids) if x is not None]
        profs = db.scalars(select(Profile).where(Profile.user_id.in_(ids))).all() if ids else []
        behaviour = db.execute(select(Answer.choice, Question.options).join(Question, Question.id == Answer.question_id)
                               .where(Answer.user_id.in_(ids), Question.kind == "behaviour")).all() if ids else []
        holds = [opts[c].lower().startswith("hold") for c, opts in behaviour if "hold" in " ".join(opts).lower()]
        avg = lambda xs: round(mean(xs), 2) if xs else None
        out[v] = {"users": len(ids), "benchmark_before_avg": avg(before), "benchmark_after_avg": avg(after),
                  "confidence_before_avg": avg([p.confidence_before for p in profs]),
                  "confidence_after_avg": avg([p.confidence_after for p in profs if p.confidence_after]),
                  "hold_share": avg([1.0 if h else 0.0 for h in holds])}
    return out
