"""SQLAlchemy models. Content tables are filled by app.seed; user tables by the API."""
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- content (from content/*.json) ----------

class Slice(Base):
    __tablename__ = "slices"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    risk: Mapped[int] = mapped_column(Integer)
    start: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer)
    content_version: Mapped[int] = mapped_column(Integer, default=1)
    nodes: Mapped[list["Node"]] = relationship(back_populates="slice", order_by="Node.position")
    __table_args__ = (CheckConstraint("risk BETWEEN 1 AND 5", name="ck_slice_risk"),)


class Node(Base):
    __tablename__ = "nodes"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    slice_key: Mapped[str] = mapped_column(ForeignKey("slices.key", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer)
    retired: Mapped[bool] = mapped_column(Boolean, default=False)
    slice: Mapped[Slice] = relationship(back_populates="nodes")
    questions: Mapped[list["Question"]] = relationship(back_populates="node", order_by="Question.position")
    requires: Mapped[list["NodeRequire"]] = relationship(foreign_keys="NodeRequire.node_id", cascade="all, delete-orphan")


class NodeRequire(Base):
    __tablename__ = "node_requires"
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True)
    requires_id: Mapped[str] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # objective | behaviour | reflection
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    answer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    why: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[list | None] = mapped_column(JSON, nullable=True)
    retired: Mapped[bool] = mapped_column(Boolean, default=False)
    node: Mapped[Node] = relationship(back_populates="questions")
    sources: Mapped[list["QuestionSource"]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (CheckConstraint("kind IN ('objective','behaviour','reflection')", name="ck_question_kind"),)


class QuestionSource(Base):
    __tablename__ = "question_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)


class BenchmarkQuestion(Base):
    __tablename__ = "benchmark_questions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    answer: Mapped[int] = mapped_column(Integer)
    why: Mapped[str] = mapped_column(Text)
    correct_pl: Mapped[int] = mapped_column(Integer)
    correct_eu: Mapped[int] = mapped_column(Integer)


class BenchmarkStat(Base):
    """Score bands and context figures from Eurobarometer 525 (pl vs eu, in %)."""
    __tablename__ = "benchmark_stats"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    pl: Mapped[int] = mapped_column(Integer)
    eu: Mapped[int] = mapped_column(Integer)


# ---------- users and activity ----------

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    variant: Mapped[str] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    profile: Mapped["Profile | None"] = relationship(back_populates="user", uselist=False)


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    age_group: Mapped[str] = mapped_column(String(10))   # 18-29 | 30-49 | 50+
    goal: Mapped[str] = mapped_column(String(20))        # habit | kids | retire
    experience: Mapped[str] = mapped_column(String(10))  # none | some | a_lot
    confidence_before: Mapped[int] = mapped_column(Integer)
    confidence_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    user: Mapped[User] = relationship(back_populates="profile")


class Answer(Base):
    __tablename__ = "answers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    choice: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # null for behaviour/reflection
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class NodeProgress(Base):
    __tablename__ = "node_progress"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BenchmarkAnswer(Base):
    __tablename__ = "benchmark_answers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(10))  # before | after
    question_id: Mapped[str] = mapped_column(ForeignKey("benchmark_questions.id"))
    choice: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("user_id", "stage", "question_id", name="uq_benchmark_once"),
        CheckConstraint("stage IN ('before','after')", name="ck_benchmark_stage"),
    )


class UserBadge(Base):
    __tablename__ = "user_badges"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    badge_key: Mapped[str] = mapped_column(String(40), primary_key=True)  # see app/badges.py BADGES
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(60), index=True)
    variant: Mapped[str | None] = mapped_column(String(4), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Attempt(Base):
    """One submission to the task engines (docs/task_engines.md, "Attempt record").
    node_id is the node the attempt counts toward: the item's own node for practice,
    the node being unlocked for a prerequisite test or test-out."""
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    task_id: Mapped[str] = mapped_column(String(40), index=True)
    node_id: Mapped[str] = mapped_column(String(10))
    level: Mapped[str] = mapped_column(String(10))       # easy | medium | hard
    context: Mapped[str] = mapped_column(String(20))     # practice | prerequisite | test_out
    content_version: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_reasons: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # null for reflections
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # hard tasks only
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    tutor_opened: Mapped[bool] = mapped_column(Boolean, default=False)
    clarity_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)            # hard: 51-100 when accepted
    growth_index: Mapped[float | None] = mapped_column(Float, nullable=True)      # hard: reference solution = 100
    failed_test: Mapped[str | None] = mapped_column(String(200), nullable=True)   # hard: first failing obligatory test
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)       # engine time to score
    __table_args__ = (
        Index("ix_attempts_user_node", "user_id", "node_id"),
        CheckConstraint("level IN ('easy','medium','hard')", name="ck_attempt_level"),
        CheckConstraint("context IN ('practice','prerequisite','test_out')", name="ck_attempt_context"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 1 AND 5", name="ck_attempt_confidence"),
        CheckConstraint("clarity_rating IS NULL OR clarity_rating BETWEEN 1 AND 5", name="ck_attempt_clarity"),
    )


# ---------- monitoring (docs/tutor_agent.md, sections 5 and 6) ----------

class LlmEvent(Base):
    """One tutor or router call to a language model. Personal data is masked
    before the text is stored (prompt_masked, answer_masked); the admin panel
    shows pseudonymous user ids only."""
    __tablename__ = "llm_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    screen_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    node: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    mode: Mapped[str | None] = mapped_column(String(30), nullable=True)        # explain_concept | hint | explain_result | ...
    intent: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)  # e.g. advice_request, injection
    model_role: Mapped[str | None] = mapped_column(String(30), nullable=True)  # tutor_small | router | tutor_cloud
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checks_failed: Mapped[list] = mapped_column(JSON, default=list)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    hint_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)    # +1 / -1
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    prompt_masked: Mapped[str | None] = mapped_column(Text, nullable=True)     # what the user asked, personal data masked
    answer_masked: Mapped[str | None] = mapped_column(Text, nullable=True)     # what the tutor answered, masked


class RecoEvent(Base):
    """One onboarding-router or recommender event (docs/tutor_agent.md, section 6)."""
    __tablename__ = "reco_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    router_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)  # path_issued | test_out | first_item | ...
    node: Mapped[str | None] = mapped_column(String(10), nullable=True)
    predicted_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    need: Mapped[float | None] = mapped_column(Float, nullable=True)
    overconfidence_term: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_term: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason_term: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # extra fields (demo_match, path_chosen, path_finished)
    path: Mapped[list | None] = mapped_column(JSON, nullable=True)


# ---------- onboarding, monitoring, feedback, study (docs/admin_and_profile.md) ----------

class Onboarding(Base):
    """The survey and the router's result, latest per user (docs/onboarding_router.md)."""
    __tablename__ = "onboarding"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    survey: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    router_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Feedback(Base):
    """'Report a problem' and post-mission feedback (docs/admin_and_profile.md, view G)."""
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    where: Mapped[str] = mapped_column(String(20))       # item | card | task | tutor_answer | screen | mission
    target_id: Mapped[str] = mapped_column(String(60), index=True)
    kind: Mapped[str] = mapped_column(String(20))        # wrong_fact | unclear | bug | idea | other | rating
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="new")   # new | triaged | fixed | wont_fix
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('new','triaged','fixed','wont_fix')", name="ck_feedback_status"),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
    )


class Consent(Base):
    """Study mode (hallway test): consent under a random participant id, no name or contact details."""
    __tablename__ = "consents"
    participant_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    consent_version: Mapped[str] = mapped_column(String(20))
    given_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PathCheckin(Base):
    """The end-of-path check-in: progress, confidence per area, next goal (docs/admin_and_profile.md)."""
    __tablename__ = "path_checkins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    path_id: Mapped[str] = mapped_column(String(30))
    answers: Mapped[dict] = mapped_column(JSON)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
