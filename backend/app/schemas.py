"""Request and response models. Every field has a description: it appears in /docs and /openapi.json,
and becomes doc comments in the generated Flutter (Dart) client. Value meanings live in app/catalog.py (GET /meta)."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal["objective", "behaviour", "reflection"]
State = Literal["done", "current", "open", "ahead"]


class SessionIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=80, description="Name shown in the app, e.g. 'Zofia'.")


class SessionOut(BaseModel):
    user_id: str = Field(description="Stable user id (UUID).")
    token: str = Field(description="Send on every request as 'Authorization: Bearer <token>'.")
    variant: str = Field(description="A/B test group, 'A' or 'B'. See GET /meta → ab_variants.")


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128, description="At least 8 characters.")
    display_name: str | None = Field(default=None, max_length=80)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AccountOut(BaseModel):
    user_id: str
    token: str = Field(description="Send on every request as 'Authorization: Bearer <token>'.")
    variant: str
    email: str | None
    display_name: str
    is_admin: bool
    share_profile: bool = False


class ProfileIn(BaseModel):
    age_group: Literal["18-29", "30-49", "50+"] = Field(description="Onboarding question 1: age band.")
    goal: Literal["habit", "kids", "retire"] = Field(description="Onboarding question 2: main goal. Decides which wheel slices are highlighted.")
    experience: Literal["none", "some", "a_lot"] = Field(description="Onboarding question 3: investing experience.")
    confidence_before: int = Field(ge=1, le=5, description="Onboarding question 4: 'How ready do you feel to invest?' 1 = not at all, 5 = fully ready.")


class ConfidenceIn(BaseModel):
    value: int = Field(ge=1, le=5, description="Same 1-5 readiness question, asked after missions (the 'after' measurement).")


class SliceOut(BaseModel):
    key: str = Field(description="Slice id, e.g. 'stocks'. Use it in GET /wheel/{key}/tree.")
    label: str = Field(description="Display name of the investment type.")
    risk: int = Field(ge=1, le=5, description="1 calm to 5 bumpy. Colour the slice with GET /meta → risk_levels.")
    start: bool = Field(description="True = recommended starting slice for beginners; show a star.")
    progress: float = Field(ge=0, le=1, description="Share of this slice's nodes the user completed (0.0-1.0). Draw as the progress ring.")
    highlight: bool = Field(description="True = matches the user's goal from onboarding; emphasise it on the wheel.")


class WheelOut(BaseModel):
    slices: list[SliceOut] = Field(description="All slices in wheel order (clockwise from the top).")


class NodeOut(BaseModel):
    id: str = Field(description="Node id, e.g. 'stocks.s3'. Use it in GET /nodes/{id}.")
    title: str = Field(description="Short topic title shown on the tree.")
    requires: list[str] = Field(description="Suggested earlier node ids (a recommendation, not a lock). Draw them as lines into this node.")
    state: State = Field(description="Decided by the backend. See GET /meta → node_states for how to draw each state.")
    hint: str | None = Field(default=None, description="Only when state='ahead': gentle suggestion, e.g. 'We suggest X first'. The node can still be opened.")


class TreeOut(BaseModel):
    slice: str = Field(description="Slice key.")
    label: str = Field(description="Slice display name for the screen title.")
    nodes: list[NodeOut] = Field(description="Nodes in learning order.")


class QuestionOut(BaseModel):
    id: str = Field(description="Question id, e.g. 'stocks.s3.q1'. Send it back in POST /answers.")
    kind: Kind = Field(description="Which card to draw. See GET /meta → question_kinds.")
    q: str = Field(description="Question text.")
    options: list[str] = Field(description="Answer options in display order. Send the chosen index as 'choice'.")


class NodeDetailOut(BaseModel):
    id: str = Field(description="Node id.")
    title: str = Field(description="Node title.")
    slice: str = Field(description="Slice key this node belongs to.")
    state: str = Field(description="Current state of the node. Every node can be opened; 'ahead' only means its suggested prerequisites are not done yet.")
    questions: list[QuestionOut] = Field(description="Questions in order. Correct answers are NOT included; they come back from POST /answers.")


class AnswerIn(BaseModel):
    question_id: str = Field(description="Question id from GET /nodes/{id}.")
    choice: int = Field(ge=0, description="Index of the chosen option (0-based).")


class BadgeOut(BaseModel):
    key: str = Field(description="Badge id, e.g. 'first_step'.")
    title: str = Field(description="Badge name to show.")
    description: str = Field(description="How it was earned.")
    icon: str = Field(description="Icon hint for the app: flag, pie, shield, medal or flame.")


class MyBadgeOut(BadgeOut):
    earned: bool = Field(description="True if the user has this badge; show the rest greyed out as goals.")
    awarded_at: str | None = Field(description="When it was earned (ISO 8601), null if not yet.")


class LeaderboardEntry(BaseModel):
    rank: int = Field(description="1 = most XP this week in the league.")
    display_name: str = Field(description="Name only; no ids or answers are ever shared.")
    weekly_xp: int = Field(description="XP earned since Monday 00:00 UTC.")
    is_me: bool = Field(description="True for the current user; highlight this row.")


class LeaderboardOut(BaseModel):
    league: int = Field(description="League number. Leagues are groups of up to 10 users, so beginners compete with a small group.")
    week_start: str = Field(description="Start of the current week (ISO 8601, Monday 00:00 UTC). The board resets weekly.")
    entries: list[LeaderboardEntry] = Field(description="League members ranked by weekly XP.")


class AnswerOut(BaseModel):
    kind: str = Field(description="Question kind, same values as QuestionOut.kind.")
    is_correct: bool | None = Field(description="Objective only: true/false. Null for behaviour and reflection (not scored).")
    correct_choice: int | None = Field(description="Objective only: index of the correct option, to highlight it green.")
    explanation: str | None = Field(description="Objective only: why the correct answer is right. Show after answering.")
    feedback: str | None = Field(description="Behaviour only: feedback for the option the user picked.")
    sources: list[str] = Field(description="URLs backing any facts in this question. Show as 'Source' links.")
    xp_awarded: int = Field(description="XP earned by this answer (0 if wrong or already rewarded).")
    node_completed: bool = Field(description="True if this answer finished the node; show a completion moment.")
    unlocked: list[str] = Field(description="Node ids whose suggested prerequisites are now all done (they move from 'ahead' to open/current); animate them on the tree.")
    new_badges: list[BadgeOut] = Field(default_factory=list, description="Badges earned by this answer; show a pop-up for each.")


class BenchmarkOption(BaseModel):
    choice: int = Field(description="Original option index. Send THIS back, not the display position.")
    text: str = Field(description="Option text.")


class BenchmarkQuestionOut(BaseModel):
    id: str = Field(description="Benchmark question id, e.g. 'eb_q2'.")
    topic: str = Field(description="What it tests, e.g. 'inflation'.")
    q: str = Field(description="Question text (based on Eurobarometer 525).")
    options: list[BenchmarkOption] = Field(description="Shuffled per user and stage, so 'after' differs from 'before'.")


class BenchmarkAnswerIn(BaseModel):
    question_id: str = Field(description="Benchmark question id.")
    choice: int = Field(ge=0, description="The option's original index (BenchmarkOption.choice).")


class BenchmarkSubmitIn(BaseModel):
    stage: Literal["before", "after"] = Field(description="'before' right after onboarding, 'after' once missions are done. Each can be submitted once.")
    answers: list[BenchmarkAnswerIn] = Field(description="Exactly one answer per benchmark question.")


class BenchmarkPerQuestion(BaseModel):
    question_id: str = Field(description="Benchmark question id.")
    topic: str = Field(description="Topic tested.")
    is_correct: bool = Field(description="Whether the user got it right.")
    why: str = Field(description="Explanation of the correct answer.")
    correct_pl: int = Field(description="% of Poles who answered correctly in Eurobarometer 525.")
    correct_eu: int = Field(description="% of EU adults who answered correctly.")


class BenchmarkResultOut(BaseModel):
    stage: str = Field(description="'before' or 'after'.")
    score: int = Field(description="Number of correct answers.")
    out_of: int = Field(description="Number of questions (5).")
    band: Literal["high", "medium", "low"] = Field(description="high = 4-5, medium = 2-3, low = 0-1 correct (Eurobarometer bands).")
    comparison: str = Field(description="Ready-to-show sentence comparing the user with Poland and the EU.")
    per_question: list[BenchmarkPerQuestion] = Field(description="Result and national comparison for each question.")
    new_badges: list[BadgeOut] = Field(default_factory=list, description="Badges earned by this submission (e.g. 'Above Poland').")


class ProgressOut(BaseModel):
    xp: int = Field(description="Total XP.")
    streak_days: int = Field(description="Consecutive days with at least one answer (today counts until midnight).")
    nodes_completed: int = Field(description="Nodes finished across all slices.")
    nodes_total: int = Field(description="All active nodes.")
    benchmark_before: int | None = Field(description="EU benchmark score before missions (null if not taken).")
    benchmark_after: int | None = Field(description="EU benchmark score after missions (null if not taken).")


# ---------- task engines (skills tree: easy items and medium tasks) ----------
# The task views come from the engines (backend/data) and differ per kind, so they are typed as objects here.
# Their shapes are documented in docs/easy_engine.md and docs/medium_engine.md ("Frontend").

AttemptContext = Literal["practice", "prerequisite", "test_out"]


class DrawnTest(BaseModel):
    items: list[str] = Field(description="Item ids drawn for this user. The same user always gets the same items.")
    passed: bool = Field(description="True when every drawn item scored 1.")


class MediumProgress(BaseModel):
    tasks: list[str] = Field(description="Medium task ids of this node.")
    best_score: float | None = Field(description="Best medium score so far (0-1), null if none attempted.")


class SkillStatus(BaseModel):
    node: str = Field(description="Skills-tree node id, e.g. 'I4'.")
    easy_done: bool = Field(description="Prerequisite test or test-out passed, or the scored items average at least 0.8 (unanswered items count as 0).")
    medium_passed: bool = Field(description="At least one medium task scored 0.6 or more.")
    done: bool = Field(description="Node complete: easy part done and a medium task passed. A node without medium tasks is done when its easy part is.")
    items_answered: int = Field(description="Scored easy items answered at least once.")
    items_total: int = Field(description="Scored easy items in the node (reflections excluded).")
    item_average: float | None = Field(description="Average of the latest score per scored item, unanswered = 0.")
    prerequisite: DrawnTest = Field(description="The prerequisite test for this node (check items from its 'after' nodes).")
    test_out: DrawnTest = Field(description="The test-out for this node (2 of its own check items).")
    medium: MediumProgress = Field(description="Medium task progress.")


class SkillSummary(BaseModel):
    id: str = Field(description="Node id, e.g. 'I4'. Use it in GET /skills/{id}.")
    title: str = Field(description="Node title.")
    panel: str = Field(description="Skills-tree panel, e.g. 'INSTRUMENTS'.")
    after: list[str] = Field(description="Suggested earlier node ids.")
    live: bool = Field(description="False until a reviewer signs the node off. Drafts are served only when SERVE_DRAFTS is on.")
    cards: int = Field(description="Number of cards.")
    items: int = Field(description="Number of easy items.")
    medium_tasks: int = Field(description="Number of medium tasks.")
    status: SkillStatus = Field(description="This user's completion of the node.")


class SkillDetail(BaseModel):
    node: dict[str, Any] = Field(description="The easy engine's node view: cards (with resolved links) and items, without answers.")
    medium: list[dict[str, Any]] = Field(description="Medium task question views for this node, without truth, weights or explanations.")
    hard: list[dict[str, Any]] = Field(default_factory=list, description="Hard task question views (Blockly blocks, toolbox, starter), without the reference solution.")
    status: SkillStatus = Field(description="This user's completion of the node.")


class DrawnTestOut(BaseModel):
    node: str = Field(description="The node this test is for.")
    context: Literal["prerequisite", "test_out"] = Field(description="Send this as 'context' (with for_node) when submitting each item.")
    items: list[dict[str, Any]] = Field(description="Easy item question views, without answers. Empty when the node has no pool.")


class TaskOut(BaseModel):
    level: Literal["easy", "medium", "hard"] = Field(description="Which engine renders it: 'easy' item, 'medium' task or 'hard' block task.")
    task: dict[str, Any] = Field(description="The question view, without answers, truth or weights.")


class CodeIn(BaseModel):
    code: str = Field(max_length=8000, description="Hard tasks: the plan written in the code panel's text form.")


class AttemptIn(BaseModel):
    response: Any = Field(description="Easy: option index (single, reflection), list of indexes (multi), boolean (true_false) or number (numeric). Medium: the direction, e.g. 'down'. Hard: the saved Blockly workspace JSON, or the program JSON.")
    reasons: list[str] | None = Field(default=None, description="Medium only: picked reason box ids, between pick.min and pick.max.")
    confidence: int | None = Field(default=None, ge=1, le=5, description="'How sure are you?' 1-5. Ask on every scored item; stored, never scored.")
    context: AttemptContext = Field(default="practice", description="'practice' for normal play; 'prerequisite' or 'test_out' when answering a drawn test, with for_node.")
    for_node: str | None = Field(default=None, description="Required for 'prerequisite' and 'test_out': the node the test unlocks.")
    started_at: datetime | None = Field(default=None, description="When the task was shown (ISO 8601), for time-on-task.")
    hints_used: int = Field(default=0, ge=0, description="Hints opened before submitting.")
    tutor_opened: bool = Field(default=False, description="True if the user opened the tutor on this task.")
    clarity_rating: int | None = Field(default=None, ge=1, le=5, description="Optional 'Was this clear?' rating, 1-5.")


class AttemptOut(BaseModel):
    attempt_id: int = Field(description="Id of the stored attempt.")
    task_id: str = Field(description="Item or task id.")
    level: Literal["easy", "medium", "hard"] = Field(description="Engine that scored it.")
    score: float | None = Field(description="0-1; null for reflections (not scored) and rejected hard programs.")
    score_estimate: float | None = Field(description="Medium estimate part; null for easy items and day-X tasks.")
    score_reasons: float | None = Field(description="Medium reasons part (0-1); null for easy items.")
    confidence: int | None = Field(description="The confidence sent, null for reflections.")
    p: float | None = Field(description="Confidence as a probability, (confidence - 1) / 4.")
    reveal: dict[str, Any] = Field(description="What to show after answering: the answer and 'why' (easy), or outcome, per-box explanations and sources (medium).")
    status: SkillStatus = Field(description="Completion of the node this attempt counts toward, after this attempt.")
    node_completed: bool = Field(description="True if this attempt completed the node; show a completion moment.")
    accepted: bool | None = Field(default=None, description="Hard only: all obligatory tests passed.")
    points: int | None = Field(default=None, description="Hard only: resilience points 51-100 when accepted.")
    growth_index: float | None = Field(default=None, description="Hard only: growth vs the reference solution = 100.")
    scales_total: int | None = Field(default=None, description="The learner's Scales after this answer.")
    record: list[Any] | None = Field(default=None, description="Guests only: the attempt record to keep in the app's history (X-Guest-History).")
