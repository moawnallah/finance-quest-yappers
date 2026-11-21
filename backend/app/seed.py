"""Loads content/wheel.json, content/slices/*.json and content/eu_benchmark.json into the database.

Idempotent upsert by id: new rows are added, changed rows updated, nothing user-related is touched.
Rows that disappeared from the content are marked retired (never deleted), so old answers keep their meaning.
Run: python -m app.seed
"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import CONTENT_DIR
from app.db import SessionLocal
from app.models import (BenchmarkQuestion, BenchmarkStat, Node, NodeRequire, Question, QuestionSource, Slice)


def _kind(q: dict) -> str:
    if "answer" in q:
        return "objective"
    if "feedback" in q:
        return "behaviour"
    return "reflection"


def seed(db: Session) -> dict:
    wheel = json.loads((CONTENT_DIR / "wheel.json").read_text())
    seen_nodes, seen_questions = set(), set()
    counts = {"slices": 0, "nodes": 0, "questions": 0, "benchmark": 0}

    for pos, key in enumerate(wheel["order"]):
        data = json.loads((CONTENT_DIR / "slices" / f"{key}.json").read_text())
        sl = db.get(Slice, key) or Slice(key=key)
        sl.label, sl.risk, sl.start, sl.position = data["label"], data["risk"], data["start"], pos
        sl.content_version = data.get("content_version", 1)
        db.add(sl)
        counts["slices"] += 1
        db.flush()

        for npos, n in enumerate(data["nodes"]):
            node = db.get(Node, n["id"]) or Node(id=n["id"])
            node.slice_key, node.title, node.position = key, n["title"], npos
            node.retired = bool(n.get("retired", False))
            db.add(node)
            seen_nodes.add(n["id"])
            counts["nodes"] += 1
        db.flush()

        for n in data["nodes"]:
            db.query(NodeRequire).filter(NodeRequire.node_id == n["id"]).delete()
            for req in n.get("after", []):
                db.add(NodeRequire(node_id=n["id"], requires_id=req))
            for qpos, q in enumerate(n["questions"]):
                row = db.get(Question, q["id"]) or Question(id=q["id"])
                row.node_id, row.position, row.kind, row.text = n["id"], qpos, _kind(q), q["q"]
                row.options, row.answer, row.why = q["options"], q.get("answer"), q.get("why")
                row.feedback, row.retired = q.get("feedback"), bool(q.get("retired", False))
                db.add(row)
                db.flush()
                db.query(QuestionSource).filter(QuestionSource.question_id == q["id"]).delete()
                for url in q.get("sources", []):
                    db.add(QuestionSource(question_id=q["id"], url=url))
                seen_questions.add(q["id"])
                counts["questions"] += 1

    # anything no longer in the content is retired, not deleted
    for node in db.scalars(select(Node).where(Node.id.not_in(seen_nodes))):
        node.retired = True
    for q in db.scalars(select(Question).where(Question.id.not_in(seen_questions))):
        q.retired = True

    bench = json.loads((CONTENT_DIR / "eu_benchmark.json").read_text())
    for pos, q in enumerate(bench["quiz"]):
        row = db.get(BenchmarkQuestion, q["id"]) or BenchmarkQuestion(id=q["id"])
        row.position, row.topic, row.text, row.options = pos, q["topic"], q["q"], q["options"]
        row.answer, row.why, row.correct_pl, row.correct_eu = q["answer"], q["why"], q["correct_pl"], q["correct_eu"]
        db.add(row)
        counts["benchmark"] += 1
    stats = {**{f"score_{k}": v for k, v in bench["score_bands"].items()}, **bench["context"]}
    for k, v in stats.items():
        row = db.get(BenchmarkStat, k) or BenchmarkStat(key=k)
        row.pl, row.eu = v["pl"], v["eu"]
        db.add(row)

    db.commit()
    return counts


if __name__ == "__main__":
    import sys
    if "--scenarios" in sys.argv:  # python -m app.seed --scenarios
        from app.synthetic import seed_scenarios
        with SessionLocal() as session:
            for row in seed_scenarios(session):
                print(row["pseudo"], row["label"])
    if "--synthetic" in sys.argv:  # python -m app.seed --synthetic 200
        from app.synthetic import seed_synthetic
        n = int(sys.argv[sys.argv.index("--synthetic") + 1]) if len(sys.argv) > sys.argv.index("--synthetic") + 1 else 200
        with SessionLocal() as session:
            print("synthetic learners:", seed_synthetic(session, n))
    else:
        with SessionLocal() as session:
            print("seeded:", seed(session))
