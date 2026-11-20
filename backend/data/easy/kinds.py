"""Easy item kinds (docs/task_engines.md, "Easy engine"), one class per kind in ITEM_KINDS.

Every kind has the same methods:
    validate(item, report)        problems in the authored item
    public(item) -> dict          fields sent before the answer (never the answer)
    reveal(item) -> dict          fields sent after the answer
    check(item, response)         None, or why the response doesn't fit
    score(item, response)         0..1, or None when not scored (reflection)
    secrets(item) -> dict         {"strings": [...], "numbers": [...]} for the tutor's leak check

To add a kind (e.g. matching or ranking), write one class like these and add it to ITEM_KINDS.
"""
from __future__ import annotations

from common import all_strings, is_text, tolerance_score


def _is_index(v, n: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v < n


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class _Options:
    """Shared by kinds with a list of options."""

    def _validate_options(self, item: dict, r):
        options = item.get("options")
        if not isinstance(options, list) or not 2 <= len(options) <= 6 or not all(is_text(o) for o in options):
            r.error(f"{item.get('id')}: options must be a list of 2-6 texts")
            return []
        return options

    def public(self, item: dict) -> dict:
        return {"options": item["options"]}


class Single(_Options):
    """One option is correct. Score 1 or 0."""

    def validate(self, item, r):
        options = self._validate_options(item, r)
        if options and not _is_index(item.get("answer"), len(options)):
            r.error(f"{item.get('id')}: answer must be the index (0-based) of one option")

    def reveal(self, item):
        return {"answer": item["answer"]}

    def check(self, item, response):
        return None if _is_index(response, len(item["options"])) else "response must be an option index"

    def score(self, item, response):
        return 1.0 if response == item["answer"] else 0.0

    def secrets(self, item):
        return {"strings": all_strings(item["options"][item["answer"]]), "numbers": []}


class Multi(_Options):
    """Several options are correct. Score (correct picks − wrong picks) / number of correct, clipped to 0-1."""

    def validate(self, item, r):
        options = self._validate_options(item, r)
        answer = item.get("answer")
        if options and (not isinstance(answer, list) or not answer or len(set(answer)) != len(answer)
                        or not all(_is_index(a, len(options)) for a in answer)):
            r.error(f"{item.get('id')}: answer must be a non-empty list of distinct option indexes")
        elif options and len(answer) == len(options):
            r.warn(f"{item.get('id')}: every option is correct, so picking all scores 1")

    def reveal(self, item):
        return {"answer": item["answer"]}

    def check(self, item, response):
        n = len(item["options"])
        ok = isinstance(response, list) and len(set(response)) == len(response) and all(_is_index(x, n) for x in response)
        return None if ok else "response must be a list of distinct option indexes"

    def score(self, item, response):
        correct = set(item["answer"])
        good = len(correct & set(response))
        bad = len(set(response) - correct)
        return min(1.0, max(0.0, (good - bad) / len(correct)))

    def secrets(self, item):
        return {"strings": [s for a in item["answer"] for s in all_strings(item["options"][a])], "numbers": []}


class TrueFalse:
    """`q` is a statement; the answer is true or false. Score 1 or 0."""

    def validate(self, item, r):
        if not isinstance(item.get("answer"), bool):
            r.error(f"{item.get('id')}: answer must be true or false")

    def public(self, item):
        return {}

    def reveal(self, item):
        return {"answer": item["answer"]}

    def check(self, item, response):
        return None if isinstance(response, bool) else "response must be true or false"

    def score(self, item, response):
        return 1.0 if response == item["answer"] else 0.0

    def secrets(self, item):
        return {"strings": [], "numbers": []}


class Numeric:
    """A number. Scored with the tolerance rule: 1 within the band, 0 at three bands.

    answer: 14400
    unit: PLN
    tolerance: {kind: relative, band: 0.05}    # or {kind: absolute, band: 100}
    input: {min: 0, max: 30000, step: 100}     # optional, for a slider
    """

    def validate(self, item, r):
        iid = item.get("id")
        if not _is_number(item.get("answer")):
            r.error(f"{iid}: answer must be a number")
        tol = item.get("tolerance") or {}
        if tol.get("kind") not in ("relative", "absolute") or not _is_number(tol.get("band")) or tol["band"] < 0:
            r.error(f"{iid}: tolerance needs kind relative|absolute and a band >= 0")
        if not isinstance(item.get("unit"), str):
            r.error(f"{iid}: unit is required (e.g. PLN, %)")
        inp = item.get("input")
        if inp is not None:
            if not all(_is_number(inp.get(k)) for k in ("min", "max", "step")) or not inp["min"] < inp["max"]:
                r.error(f"{iid}: input needs numbers min < max and step")
            elif _is_number(item.get("answer")) and not inp["min"] <= item["answer"] <= inp["max"]:
                r.error(f"{iid}: the answer is outside input min..max")

    def public(self, item):
        out = {"unit": item["unit"]}
        if item.get("input"):
            out["input"] = item["input"]
        return out

    def reveal(self, item):
        return {"answer": item["answer"], "unit": item["unit"], "tolerance": item["tolerance"]}

    def check(self, item, response):
        return None if _is_number(response) else "response must be a number"

    def score(self, item, response):
        t = item["tolerance"]
        return tolerance_score(float(response), float(item["answer"]), t["kind"], float(t["band"]))

    def secrets(self, item):
        return {"strings": [], "numbers": [item["answer"]]}


class Reflection(_Options):
    """No correct answer and not scored. Each option has its own feedback (behaviour questions)."""

    def validate(self, item, r):
        options = self._validate_options(item, r)
        fb = item.get("feedback")
        if options and (not isinstance(fb, list) or len(fb) != len(options) or not all(is_text(f) for f in fb)):
            r.error(f"{item.get('id')}: feedback must have one text per option")
        if "answer" in item:
            r.error(f"{item.get('id')}: a reflection has no answer")

    def reveal(self, item):
        return {"feedback": item["feedback"]}

    def check(self, item, response):
        return None if _is_index(response, len(item["options"])) else "response must be an option index"

    def score(self, item, response):
        return None

    def secrets(self, item):
        return {"strings": [], "numbers": []}


ITEM_KINDS = {
    "single": Single(),
    "multi": Multi(),
    "true_false": TrueFalse(),
    "numeric": Numeric(),
    "reflection": Reflection(),
}
SCORED = {k for k in ITEM_KINDS if k != "reflection"}
