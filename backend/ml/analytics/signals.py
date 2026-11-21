"""Adviser signals: when a learner's progress makes a conversation with an adviser timely.

Signals name a TYPE of instrument or account, never a product, issuer or ticker: they are prompts
for a conversation in which the adviser does the suitability assessment (MiFID II Art. 24;
Delegated Regulation 2017/565, Art. 9 and recital 15). Every text is checked with the tutor's
check_advice in the tests.
"""
from __future__ import annotations

# Named products and firms that must never appear in a signal (the same idea as the tutor's denylist).
DENYLIST = ["Nvidia", "Apple", "Tesla", "Microsoft", "Amazon", "CD Projekt", "Allegro", "Orlen", "PKO BP", "PZU",
            "mBank", "Pekao", "Vanguard", "iShares", "Xtrackers", "Bitcoin", "Ethereum"]

GOALS = {"buffer": "an emergency buffer", "first_investment": "a first investment", "retirement": "retirement",
         "home": "a home", "other": "another goal"}
HORIZONS = {"under_3": "under 3 years", "3_10": "3 to 10 years", "over_10": "over 10 years"}

# (topic, nodes that must be done, extra condition on the survey)
RULES = [
    ("an emergency fund and a savings account", ["S1"], lambda s: s.get("goal") == "buffer" or s.get("buffer") in (None, "none", "under_1")),
    ("deposits and retail bonds", ["I2"], lambda s: s.get("horizon") in ("under_3", "3_10")),
    ("index funds", ["I5", "P1"], lambda s: s.get("goal") in ("first_investment", "retirement", "other") and s.get("horizon") == "over_10"),
    ("index funds", ["I4", "P1"], lambda s: s.get("goal") in ("first_investment", "retirement", "other") and s.get("horizon") == "over_10"),
    ("retirement accounts such as IKE and IKZE", ["P2"], lambda s: s.get("goal") == "retirement"),
    ("paying down costly consumer debt first", ["F1"], lambda s: "consumer_loan" in (s.get("products") or [])),
]


def adviser_signals(learners: list[dict]) -> list[dict]:
    """learners: [{"pseudo", "survey", "done": set of node ids, "confidence": 1-5 or None}].
    One signal per learner and topic, the strongest first (more finished nodes)."""
    out = []
    for l in learners:
        s, done = l.get("survey") or {}, set(l.get("done") or ())
        seen = set()
        for topic, need, cond in RULES:
            if topic in seen or not set(need) <= done or not cond(s):
                continue
            seen.add(topic)
            parts = [f"finished {' and '.join(need)}", f"goal {GOALS.get(s.get('goal'), 'not given')}",
                     f"horizon {HORIZONS.get(s.get('horizon'), 'not given')}"]
            if l.get("confidence"):
                parts.append(f"confidence {l['confidence']}/5")
            out.append({"pseudo": l["pseudo"], "topic": topic, "nodes": need, "synthetic": bool(l.get("synthetic")),
                        "text": f"Ready to talk about {topic}: " + ", ".join(parts)})
    return sorted(out, key=lambda x: (-len(x["nodes"]), x["topic"], x["pseudo"]))
