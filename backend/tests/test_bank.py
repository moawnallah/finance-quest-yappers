"""Task group E: consent, learner cards, adviser signals, AI quality, export."""
import csv
import io

ADMIN = {"X-Admin-Key": "test-admin-key"}


def test_synthetic_seed_and_bank_views(client):
    from app.admin import pseudo
    from app.db import SessionLocal
    from app.models import User
    from app.synthetic import seed_synthetic
    with SessionLocal() as db:
        seed_synthetic(db, 40)
    ls = client.get("/admin/learners", headers=ADMIN).json()
    assert ls["synthetic"] is True and len(ls["learners"]) >= 40
    card = client.get(f"/admin/learners/{ls['learners'][0]['pseudo']}", headers=ADMIN).json()
    assert card["synthetic"] and "summary" in card and "need_reasons" in card and "timeline" in card
    sig = client.get("/admin/adviser-signals", headers=ADMIN).json()
    assert sig["signals"] and all("Ready to talk about" in s["text"] for s in sig["signals"])
    q = client.get("/admin/ai-quality", headers=ADMIN).json()
    assert q["recommended"] >= 40 and q["tutor"]["n"] >= 1
    # a registered learner without consent: no card, not in row-level exports
    a = client.post("/auth/register", json={"email": "private@example.com", "password": "a-long-password"}).json()
    h = {"Authorization": f"Bearer {a['token']}"}
    client.post("/onboarding", headers=h, json={"age_band": "25-39", "goal": "buffer", "horizon": "3_10"})
    assert client.get(f"/admin/learners/{pseudo(a['user_id'])}", headers=ADMIN).status_code == 404
    rows = list(csv.reader(io.StringIO(client.get("/admin/export?table=surveys", headers=ADMIN).text)))
    assert rows[0][0] == "user" and pseudo(a["user_id"]) not in {r[0] for r in rows[1:]}
    assert len(rows) == 1  # synthetic rows only with synthetic=1
    syn = list(csv.reader(io.StringIO(client.get("/admin/export?table=surveys&synthetic=1", headers=ADMIN).text)))
    assert len(syn) > 40
    # with consent the learner appears; withdrawing removes them again
    assert client.put("/me/consent", headers=h, json={"share": True}).json()["share_profile"] is True
    assert client.get(f"/admin/learners/{pseudo(a['user_id'])}", headers=ADMIN).status_code == 200
    rows = list(csv.reader(io.StringIO(client.get("/admin/export?table=surveys", headers=ADMIN).text)))
    assert pseudo(a["user_id"]) in {r[0] for r in rows[1:]}
    client.put("/me/consent", headers=h, json={"share": False})
    assert client.get(f"/admin/learners/{pseudo(a['user_id'])}", headers=ADMIN).status_code == 404
    assert client.get("/admin/export?table=nope", headers=ADMIN).status_code == 400
    with SessionLocal() as db:  # synthetic learners never enter leagues (no account)
        assert db.query(User).filter(User.synthetic.is_(True), User.email.isnot(None)).count() == 0


def test_scenarios_tell_their_stories(client):
    """The named demo scenarios end in the signals their stories promise, and seeding twice adds nothing."""
    from app.db import SessionLocal
    from app.synthetic import seed_scenarios
    with SessionLocal() as db:
        first = seed_scenarios(db)
        assert seed_scenarios(db) == first
    h = ADMIN
    ls = {x["label"]: x for x in client.get("/admin/learners", headers=h).json()["learners"] if x.get("label")}
    assert len(ls) == 6 and ls["Ola, 22: student with a card loan, no buffer"]["progress"] > 0
    sig = client.get("/admin/adviser-signals", headers=h).json()["signals"]
    by = {}
    for s in sig:
        by.setdefault(s["label"], set()).add(s["topic"])
    assert by["Ola, 22: student with a card loan, no buffer"] >= {"an emergency fund and a savings account", "paying down costly consumer debt first"}
    assert "index funds" in by["Tomek, 31: first investment, long horizon"]
    assert by["Ewa, 58: retirement in 3 to 10 years"] >= {"deposits and retail bonds", "retirement accounts such as IKE and IKZE"}
    assert "deposits and retail bonds" in by["Kasia, 27: saving for a home"]
    assert "Marek, 35: confident, but struggling with funds" not in by and "Julia, 24: just started" not in by
    card = client.get(f"/admin/learners/{ls['Tomek, 31: first investment, long horizon']['pseudo']}", headers=h).json()
    assert card["label"].startswith("Tomek") and card["need_reasons"][0]["node"] == "I4"


def test_adviser_panel_aggregates(client):
    from app.db import SessionLocal
    from app.synthetic import seed_scenarios
    with SessionLocal() as db:
        seed_scenarios(db)
    d = client.get("/admin/adviser-signals", headers=ADMIN).json()
    s = d["summary"]
    assert s["learners"] >= 6 and s["ready"] == len({x["pseudo"] for x in d["signals"]}) >= 4 and s["ready"] <= s["learners"]
    assert s["products"]["consumer_loan"].get("18-24", 0) >= 1 and sum(s["products"]["life_insurance"].values()) >= 2
    assert all({"age_band", "confidence", "products"} <= set(x) for x in d["signals"])
