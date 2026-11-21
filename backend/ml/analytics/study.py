"""Study mode (hallway test): consent text and anonymous participant ids (docs/admin_and_profile.md)."""
from __future__ import annotations

import secrets

CONSENT_VERSION = "2026-11-21"
CONSENT_TEXT = (
    "We are testing a student project at Collabothon. We record your answers, how sure you were, and how long "
    "you took, under a random code. We do not record your name or contact details. You can stop at any time, "
    "and ask us to delete your answers using your code."
)
ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0, O, 1 or I, so codes are easy to read out


def participant_id(existing: set[str], length: int = 4) -> str:
    """A new code like FQ-7K3P that is not in `existing`."""
    for _ in range(10_000):
        code = "FQ-" + "".join(secrets.choice(ALPHABET) for _ in range(length))
        if code not in existing:
            return code
    raise RuntimeError("no free participant id; use a longer code")
