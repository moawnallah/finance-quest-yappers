"""Output checks (docs/tutor_agent.md, section 4). Each returns a list of problems; empty = pass.

These are the safety layer between the model and the user. Any problem means the user sees the
stored explanation instead of the model's answer.
"""
from __future__ import annotations

import re

MAX_WORDS = 200
FREE_SMALL_INT = 10  # integers 1..10 are allowed anywhere ("two reasons", "step 3")

_SEP = r"[,   ]"  # thousands separators: comma, no-break space, thin space, space
NUMBER_RE = re.compile(rf"(?<![\w.])\d{{1,3}}(?:{_SEP}\d{{3}})+(?:\.\d+)?|(?<![\w.])\d+(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    """Absolute values of the numbers in a text. Signs and ranges ("1976-2025") are ignored."""
    return [float(re.sub(_SEP, "", m)) for m in NUMBER_RE.findall(text)]


def _decimals(x: float) -> int:
    s = repr(x)
    return len(s.split(".")[1].rstrip("0")) if "." in s else 0


def _matches(x: float, allowed: list[float]) -> bool:
    for c in allowed:
        if x == round(c, _decimals(x)) or abs(x - c) <= 0.005 * abs(c):
            return True
    return False


def check_numbers(text: str, context_text: str) -> list[str]:
    """Every number in the answer must come from the context (within rounding)."""
    base = numbers_in(context_text)
    allowed = base + [c * 100 for c in base if c < 1] + [c / 100 for c in base]
    bad = [x for x in numbers_in(text) if not (x.is_integer() and x <= FREE_SMALL_INT) and not _matches(x, allowed)]
    return [f"number not in context: {x:g}" for x in bad]


ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")
TICKER_RES = [
    re.compile(r"\$[A-Z]{1,5}\b"),
    re.compile(r"\b(?:NYSE|NASDAQ|GPW|WSE|LSE|XETRA)\s*:\s*[A-Z0-9.]{1,8}\b"),
]
ADVICE_RES = [
    re.compile(r"\byou should (?:buy|sell|invest in|put your money in)\b", re.I),
    re.compile(r"\bi (?:would )?recommend (?:buying|selling|investing in)\b", re.I),
    re.compile(r"\b(?:buy|sell) (?:now|this|these|it|them)\b", re.I),
    re.compile(r"\bthe best (?:fund|stock|etf|bank|broker) (?:is|for you)\b", re.I),
]


def check_advice(text: str, denylist: list[str] = ()) -> list[str]:
    """No product identifiers, no named products or firms from the denylist, no buy/sell advice."""
    problems = []
    if ISIN_RE.search(text):
        problems.append("ISIN")
    if any(r.search(text) for r in TICKER_RES):
        problems.append("ticker")
    for r in ADVICE_RES:
        m = r.search(text)
        if m:
            problems.append(f"advice phrase: {m.group(0)!r}")
    for name in denylist:
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text, re.I):
            problems.append(f"named product or firm: {name!r}")
    return problems


def check_leak(text: str, secrets: dict) -> list[str]:
    """Before submission: no truth value, no correct box text or id may appear."""
    problems = []
    low = text.lower()
    for s in secrets.get("strings", []):
        if len(s) >= 4 and s.lower() in low:
            problems.append(f"leaks {s!r}")
    secret_numbers = [float(n) for n in secrets.get("numbers", [])]
    for x in numbers_in(text):
        if not (x.is_integer() and x <= FREE_SMALL_INT) and _matches(x, [abs(n) for n in secret_numbers]):
            problems.append(f"leaks the number {x:g}")
    return problems


def check_citations(cited: list[str], provided: list[str]) -> list[str]:
    """Cited labels must have been provided; when passages were provided, at least one is cited."""
    problems = [f"unknown citation {c!r}" for c in cited if c not in provided]
    if provided and not cited:
        problems.append("no citation although passages were provided")
    return problems


def check_form(text: str, check_question: str, max_words: int = MAX_WORDS) -> list[str]:
    problems = []
    if not text.strip():
        problems.append("empty answer")
    if len(text.split()) > max_words:
        problems.append(f"longer than {max_words} words")
    if not check_question.strip():
        problems.append("no check question")
    return problems
