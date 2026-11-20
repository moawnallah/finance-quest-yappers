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


PRODUCT = r"(?:fund|stock|share|etf|bond|bank|broker|crypto|coin|deposit|investment)s?"
ADVICE = re.compile("|".join([
    rf"\b(?:which|what) {PRODUCT}\b.{{0,40}}\b(?:buy|choose|pick|invest|best|sell)\b",
    rf"\b(?:which|what) is the best {PRODUCT}\b",
    rf"\bis .{{1,40}} a good (?:stock|share|fund|etf|investment|buy)\b",
    r"\bshould i (?:buy|sell|invest)\b",
    r"\bwhat should i (?:buy|invest|put)\b",
    r"\bwhere (?:should|do) i (?:put|invest)\b",
    r"\brecommend (?:me )?(?:a|an|some|any)\b",
    r"\bjak(?:i|ą|ie|a) (?:fundusz\w*|etf\w*|bank\w*|kryptowalut\w*|akcj\w*|obligacj\w*|lokat\w*)",
    r"\bktór(?:y|ą|e|a) (?:bank|fundusz|etf|broker|lokat\w*|akcj\w*)",
    r"\bw co (?:za)?inwestowa[ćc]\b",
    r"\bczy warto (?:kupi[ćc]|inwestowa[ćc]|sprzeda[ćc])\b",
    r"\bco kupi[ćc]\b|\bczy (?:kupi[ćc]|sprzeda[ćc])\b|\bpolec(?:isz|asz)\b",
]), re.I)
INJECTION = re.compile("|".join([
    r"\b(?:ignore|forget) (?:all |the )?(?:your |previous |above |prior )?(?:instructions|rules)\b",
    r"\bsystem prompt\b|\byou are now\b|\bdeveloper mode\b|\bjailbreak\b",
    r"\bpretend (?:you are|to be)\b|\brole-?play\b",
    r"\brepeat the (?:text|words|instructions) above\b",
    r"\bzignoruj (?:poprzednie|wcześniejsze)\b|\bzapomnij (?:o )?(?:zasadach|regułach|instrukcjach)\b",
    r"\budawaj\b|\bprompt\w* systemow\w*",
]), re.I)


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
