"""Rule layer before the model: personal-data masking and the intents that never reach the model.

The model-based router (role `router`) comes later; these rules stay in front of it.
"""
from __future__ import annotations

import re

MASKS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,4})?\b"), "[iban]"),
    (re.compile(r"\b\d{26}\b"), "[account]"),
    (re.compile(r"\b\d{11}\b"), "[pesel]"),
    (re.compile(r"(?<!\d)(?:\+48[ -]?)?\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)"), "[phone]"),
]


def mask(text: str) -> str:
    for pattern, label in MASKS:
        text = pattern.sub(label, text)
    return text


ADVICE = re.compile(
    r"\b(which|what) (fund|stock|share|etf|bond|bank|broker|crypto|coin)s?\b.*\b(buy|choose|pick|invest|best)\b"
    r"|\bshould i (buy|sell|invest)\b|\bwhat (should|to) i (buy|invest)\b|\brecommend (me )?(a|an|some)\b"
    r"|\bjaki (fundusz|etf|bank)\b|\bco (kupić|kupic)\b|\bczy (kupić|kupic|sprzedać|sprzedac)\b|\bpolec(isz|asz)\b",
    re.I,
)
INJECTION = re.compile(
    r"\bignore (all |the )?(previous|above|prior|your) (instructions|rules)\b|\bsystem prompt\b"
    r"|\byou are now\b|\bdeveloper mode\b|\bjailbreak\b|\bzignoruj (poprzednie|wcześniejsze)\b",
    re.I,
)


def rule_intent(message: str) -> str | None:
    """Return an intent that is answered by a template, or None to continue with the request's mode."""
    if INJECTION.search(message):
        return "injection"
    if ADVICE.search(message):
        return "advice_request"
    return None


TEMPLATES = {
    "advice_request": (
        "I can't tell you which product to buy, and nobody in this app will. What I can do is show you how "
        "to compare products yourself: read the 'What are the costs?' and risk sections of their Key "
        "Information Documents, check the firm in the KNF register, and match the product to your goal "
        "and horizon. The node 'Information and advisers' (O2) walks through it.",
        "Which two sections of a KID would you compare first?",
    ),
    "injection": (
        "I can only help with the learning content in this app: the cards, the tasks and your results.",
        "Which part of the current task would you like explained?",
    ),
}
