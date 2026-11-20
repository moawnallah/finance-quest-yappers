"""Helpers shared by the task engines (medium/, easy/). Import as `import common` from backend/data."""
from __future__ import annotations

import copy
import datetime as dt
import re
from pathlib import Path

import yaml

LANGS = {"en", "pl"}

# Words that give away an outcome or rely on hindsight. Matched as whole words, case-insensitive.
HINDSIGHT = [
    "would later", "went on to", "turned out", "in hindsight", "eventually", "famous", "infamous",
    "collapse", "collapsed", "soared", "plunged", "skyrocketed", "crashed", "record-breaking",
]


class AttemptError(ValueError):
    """The answer doesn't fit the task or item."""


class Report:
    """Collects problems while validating or compiling one task or item."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)


def read_yaml(path: Path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


CONTENT = Path(__file__).resolve().parent.parent / "content"


def load_sources(content: Path = CONTENT) -> dict[str, dict]:
    """The source register, backend/content/sources.yaml, as {id: entry}."""
    path = Path(content) / "sources.yaml"
    return {s["id"]: s for s in (read_yaml(path) or [])} if path.exists() else {}


def check_source_ids(owner: str, ids, sources: dict, r: "Report", field: str = "sources"):
    """Every id must be in the register; a licence still `to_check` is a warning."""
    if not isinstance(ids, list):
        r.error(f"{owner}: {field} must be a list of source ids")
        return
    for sid in ids:
        if sid not in sources:
            r.error(f"{owner}: unknown source {sid!r} (add it to backend/content/sources.yaml)")
        elif str(sources[sid].get("licence", "to_check")).startswith("to_check"):
            r.warn(f"{owner}: licence of source {sid!r} is not checked yet")


def load_nodes(nodes_dir: Path) -> list[tuple[str, dict]]:
    """Every node file in backend/content/nodes as (file name, data). Files starting with _ are skipped.

    Node file: node, panel, title, after, author, reviewer, status, cards, items, medium, hard
    (docs/skills_tree.md, "Learn tree and Explore wheel").
    """
    out = []
    for path in sorted(Path(nodes_dir).glob("*.yaml")):
        if not path.name.startswith("_"):
            out.append((path.name, read_yaml(path) or {}))
    return out


# ---------------------------------------------------------------- text

def is_text(v) -> bool:
    """A user-facing text is a plain string (English) or a map {en: ..., pl: ...} with `en`."""
    if isinstance(v, str):
        return bool(v.strip())
    return isinstance(v, dict) and isinstance(v.get("en"), str) and bool(v["en"].strip()) \
        and all(isinstance(x, str) for x in v.values())


def all_strings(v) -> list[str]:
    return [v] if isinstance(v, str) else [x for x in v.values() if isinstance(x, str)] if isinstance(v, dict) else []


def localize(v, lang: str = "en"):
    if isinstance(v, dict):
        return (v.get(lang) or v.get("en") or "").strip()
    return v.strip() if isinstance(v, str) else v


def localize_all(value, lang: str = "en"):
    """Turn every {en, pl} map inside `value` into a string in `lang` (English fallback). Returns a copy."""
    if isinstance(value, dict):
        if value and set(value) <= LANGS and "en" in value:
            return localize(value, lang)
        return {k: localize_all(v, lang) for k, v in value.items()}
    if isinstance(value, list):
        return [localize_all(v, lang) for v in value]
    return copy.deepcopy(value)


def has_word(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.IGNORECASE) is not None


def as_date(v):
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v))
    except ValueError:
        return None


# ---------------------------------------------------------------- numbers

def tolerance_score(answer: float, truth: float, kind: str, band: float) -> float:
    """The spec's estimate rule: 1 within the band, then linearly down to 0 at three bands.

    kind relative: the band is band x |truth|; kind absolute: the band is `band` itself.
    """
    d = band * abs(truth) if kind == "relative" else band
    if d <= 0:
        return 1.0 if answer == truth else 0.0
    r = abs(answer - truth) / d
    return 1.0 if r <= 1 else max(0.0, 1 - (r - 1) / 2)
