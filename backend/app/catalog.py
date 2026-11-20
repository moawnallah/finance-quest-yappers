"""Data catalogue served at GET /meta: what each coded value means and how the app should show it.
Field-level descriptions live on the schemas (see /docs); this file explains the values inside those fields."""

from app.badges import BADGES

CATALOG = {
    "version": 1,
    "risk_levels": {
        "1": {"label": "Calm", "meaning": "Value barely moves; main risk is inflation.", "colour": "#1F7A55"},
        "2": {"label": "Low", "meaning": "Small swings; usually paid back as agreed.", "colour": "#3D8B5E"},
        "3": {"label": "Medium", "meaning": "Clear ups and downs, spread across many holdings.", "colour": "#A86516"},
        "4": {"label": "High", "meaning": "Big swings; can fall 30-80% in a crash.", "colour": "#B5401F"},
        "5": {"label": "Bumpy", "meaning": "Can lose everything fast, or more than you put in. Complex.", "colour": "#7F1D1D"},
        "_note": "Typical, educational rule of thumb, not advice.",
    },
    "node_states": {
        "done": {"meaning": "All questions finished.", "ui": "Green with a check mark, full progress bar."},
        "current": {"meaning": "The recommended next node.", "ui": "Blue highlight; open it with a tap."},
        "open": {"meaning": "Ready (suggested earlier nodes done) but not the recommended next one.", "ui": "Normal style; can be opened."},
        "ahead": {"meaning": "Suggested earlier nodes are not done yet. Still fully open: the learner chooses.",
                  "ui": "Dimmed (no lock); tapping opens it and shows the hint, e.g. 'We suggest X first'."},
        "_note": "Nothing is ever locked. 'requires' is a recommended order, not a gate.",
    },
    "question_kinds": {
        "objective": {"card": "multiple_choice", "scored": True,
                      "ui": "Show options; after answering highlight correct_choice and show explanation + sources."},
        "behaviour": {"card": "what_would_you_do", "scored": False,
                      "ui": "Show options; after answering show the feedback for the chosen option. Never show a red X."},
        "reflection": {"card": "reflection_choice", "scored": False,
                       "ui": "Show options as a personal choice; no right or wrong, just save it."},
    },
    "onboarding": {
        "age_group": {"18-29": "Young adult", "30-49": "Mid-life", "50+": "Close to or in retirement"},
        "goal": {"habit": "Start an investing habit", "kids": "Save for children", "retire": "Prepare for retirement"},
        "experience": {"none": "Never invested", "some": "Some experience", "a_lot": "Experienced investor"},
        "confidence": {"1": "Not at all ready", "5": "Fully ready"},
    },
    "benchmark": {
        "stages": {"before": "Taken right after onboarding (baseline).", "after": "Taken after missions (to measure learning)."},
        "bands": {"high": "4-5 correct", "medium": "2-3 correct", "low": "0-1 correct"},
        "source": "Flash Eurobarometer 525 (2023). Present as 'based on the EU's Eurobarometer questions'.",
    },
    "ab_variants": {
        "A": "Wrong answers show the fixed explanation.",
        "B": "Reserved for the AI tutor explanation (not built yet); until then A and B behave the same.",
    },
    "xp": {"objective_correct": 10, "behaviour_or_reflection": 5, "_note": "Awarded once per question."},
    "streak": "Consecutive days with at least one answer; today counts until midnight.",
    "badges": {k: {"title": v["title"], "description": v["description"], "icon": v["icon"]} for k, v in BADGES.items()},
    "leaderboard": "Leagues of up to 10 users (grouped by sign-up order), ranked by XP earned since Monday 00:00 UTC. Names only.",
    "errors": {
        "shape": {"error": {"code": "machine-readable code", "message": "human-readable text", "request_id": "for support/logs"}},
        "codes": {
            "unauthorized": "Missing or unknown token; log in again.",
            "not_found": "Slice, node or question id does not exist.",
            "invalid_request": "Body or query failed validation.",
            "invalid_choice": "choice index out of range.",
            "incomplete": "Benchmark answers missing or duplicated.",
            "already_submitted": "That benchmark stage was already taken.",
            "no_profile": "Save the onboarding profile first.",
            "forbidden": "Admin key missing or wrong (admin endpoints only).",
        },
    },
}
