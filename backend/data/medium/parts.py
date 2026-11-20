"""The parts of a medium task (docs/task_engines.md, "Medium engine"), one registry per part.

    STIMULI[kind]    what the user sees            implemented: chart
    RESPONSES[kind]  what the user gives           implemented: direction
    TRUTHS[kind]     where the correct value is    implemented: none (day X), outcome
    reasons          weighted boxes, same for every task

To add a kind (e.g. stimulus `offer`, response `number`, truth `calculator`), write one class
with the same methods as its neighbours and add it to the registry. Nothing else changes.

Every compile step returns `public` (safe before the answer) and `private` (the reveal).
"""
from __future__ import annotations

import bisect
import re

from common import Report, all_strings, as_date, is_text, localize  # shared helpers (re-exported)

from .series import TRANSFORM_UNIT, TRANSFORMS, DataError, SeriesStore


# ---------------------------------------------------------------- stimuli

STEP_UNIT = {"daily": "trading_day", "monthly": "month"}


class ChartStimulus:
    """A line chart of one or more series, cut at `cutoff`. series[0] is the one the question is about.

    kind: chart
    type: line
    cutoff: 2024-04-25          # last day the user sees; the rest is shown in the reveal
    hide: [name, dates]         # anonymise: labels instead of names, day offsets instead of dates
    series:
      - {series_id: x, from: 2024-01-01, to: 2024-07-31, transform: index100, label: "Company X"}
    """

    def validate(self, spec: dict, store: SeriesStore, r: Report):
        if spec.get("type", "line") != "line":
            r.error("chart.type: only 'line' is implemented")
        if as_date(spec.get("cutoff")) is None:
            r.error("chart.cutoff must be a date")
        hide = spec.get("hide", [])
        if not set(hide) <= {"name", "dates"}:
            r.error("chart.hide may contain only name and dates")
        series = spec.get("series")
        if not isinstance(series, list) or not series:
            r.error("chart.series must be a non-empty list")
            return
        for s in series:
            sid = s.get("series_id")
            meta = store.meta(sid)
            if meta is None:
                r.error(f"chart: unknown series_id {sid!r}")
                continue
            if not meta.get("display"):
                r.error(f"chart: series {sid!r} may not be displayed (licence not cleared in catalog.yaml)")
            if s.get("transform", "level") not in TRANSFORMS:
                r.error(f"chart: transform {s.get('transform')!r} not implemented ({sorted(TRANSFORMS)})")
            for key in ("from", "to"):
                if key in s and as_date(s[key]) is None:
                    r.error(f"chart: series {sid} {key} must be a date")
            if "name" in hide and not is_text(s.get("label")):
                r.error(f"chart: series {sid} needs a `label` because the name is hidden")

    def hidden_words(self, spec: dict, store: SeriesStore) -> list[str]:
        """Names that must not appear in visible text when the name is hidden."""
        if "name" not in spec.get("hide", []):
            return []
        words = []
        for s in spec["series"]:
            meta = store.meta(s["series_id"]) or {}
            words += [meta.get("name"), *meta.get("aliases", [])]
        return [w for w in words if isinstance(w, str) and len(w) >= 2]

    def compile(self, spec: dict, store: SeriesStore, r: Report, ctx: dict):
        cutoff = as_date(spec["cutoff"])
        hide = set(spec.get("hide", []))
        public_series, private_series = [], []
        for n, s in enumerate(spec["series"]):
            series = store.get(s["series_id"])
            meta, dates = series.meta, series.dates
            freq = meta.get("frequency", "daily")
            lookup = cutoff.replace(day=1) if freq == "monthly" else cutoff
            cut = bisect.bisect_right(dates, lookup) - 1
            if cut < 0:
                raise DataError(f"{series.series_id}: no data on or before the cutoff {cutoff}")
            if freq == "daily" and (lookup - dates[cut]).days > 5:
                raise DataError(f"{series.series_id}: data gap, last observation before {cutoff} is {dates[cut]}")
            if dates[cut] != lookup:
                r.warn(f"{series.series_id}: cutoff {cutoff} not in data, using {dates[cut]}")

            transform = s.get("transform", "level")
            values = TRANSFORMS[transform](dates, series.values, cut)
            lo = bisect.bisect_left(dates, as_date(s["from"])) if "from" in s else 0
            hi = bisect.bisect_right(dates, as_date(s["to"])) - 1 if "to" in s else len(dates) - 1
            if not lo < cut < hi:
                raise DataError(f"{series.series_id}: the window must have data before and after the cutoff")

            def points(a: int, b: int) -> list[dict]:
                out = []
                for i in range(a, b + 1):
                    if values[i] is None:
                        continue
                    p = {"t": i - cut, "v": round(values[i], 4)}
                    if "dates" not in hide:
                        p["d"] = dates[i].isoformat()
                    out.append(p)
                return out

            unit = TRANSFORM_UNIT[transform] or meta.get("unit", "")
            label = s.get("label") if "name" in hide else (s.get("label") or meta.get("name"))
            public_series.append({"label": label, "unit": unit, "points": points(lo, cut)})
            private_series.append({"label": label, "name": meta.get("name"), "unit": unit, "points": points(cut, hi)})
            if n == 0:
                ctx["primary"] = {"values": values, "cut": cut, "transform": transform, "unit": unit,
                                  "frequency": freq, "series_id": series.series_id}
            ctx.setdefault("cutoff_used", dates[cut].isoformat())
            ctx.setdefault("attribution", [])
            ctx.setdefault("synthetic", False)
            if meta.get("synthetic"):
                ctx["synthetic"] = True
            else:
                ctx["attribution"].append({"source": meta.get("source"), "licence": meta.get("licence")})

        freq = ctx["primary"]["frequency"]
        public = {
            "kind": "chart",
            "type": "line",
            "x_unit": STEP_UNIT[freq] if "dates" in hide else "date",
            "series": public_series,
            "synthetic": ctx["synthetic"],  # the app must label synthetic data as such
            "attribution": ctx["attribution"],
        }
        private = {"kind": "chart", "series": private_series, "cutoff": cutoff.isoformat()}
        return public, private


STIMULI = {"chart": ChartStimulus()}


# ---------------------------------------------------------------- responses

HORIZONS = {
    "daily": {"1d": 1, "1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252},
    "monthly": {"1m": 1, "3m": 3, "6m": 6, "1y": 12},
}


def default_flat_band(steps: int, freq: str) -> float:
    """% band for index100 series: 1d 1 %, up to 1w 2 %, up to 1m 3 %, longer 5 %."""
    days = steps if freq == "daily" else steps * 21
    return 1.0 if days <= 1 else 2.0 if days <= 5 else 3.0 if days <= 21 else 5.0


class DirectionResponse:
    """Up / down / flat over a horizon after the cutoff, measured on the chart's first series.

    kind: direction
    options: [up, down, flat]
    horizon: 1w              # label or a number of observations
    flat_band: 2.0           # |change| within the band counts as flat; % for index100, else the unit
    expected: down           # what the author believes happened; the build checks it against the data
    """

    def validate(self, spec: dict, r: Report):
        options = spec.get("options", ["up", "down", "flat"])
        if not options or not set(options) <= {"up", "down", "flat"} or len(set(options)) != len(options):
            r.error("direction.options must be distinct values from up, down, flat")
        if spec.get("expected") is not None and spec["expected"] not in options:
            r.error("direction.expected must be one of the options")
        h = spec.get("horizon")
        if not (isinstance(h, int) and h > 0) and not any(h in m for m in HORIZONS.values()):
            r.error(f"direction.horizon {h!r}: use a positive integer or one of 1d 1w 2w 1m 3m 6m 1y")

    def public(self, spec: dict, ctx: dict) -> dict:
        freq = ctx["primary"]["frequency"]
        return {"kind": "direction", "options": spec.get("options", ["up", "down", "flat"]),
                "horizon": {"label": str(spec["horizon"]), "steps": self._steps(spec, freq), "unit": STEP_UNIT[freq]}}

    def _steps(self, spec: dict, freq: str) -> int | None:
        h = spec["horizon"]
        return h if isinstance(h, int) else HORIZONS[freq].get(h)

    def outcome(self, spec: dict, ctx: dict, r: Report) -> dict | None:
        p = ctx["primary"]
        steps = self._steps(spec, p["frequency"])
        if steps is None:
            r.error(f"direction.horizon {spec['horizon']!r} is not valid for {p['frequency']} data")
            return None
        values, cut = p["values"], p["cut"]
        if cut + steps >= len(values) or values[cut + steps] is None or values[cut] is None:
            r.error(f"not enough data after the cutoff for horizon {spec['horizon']}")
            return None
        percent = p["transform"] == "index100"
        change = round(values[cut + steps] - values[cut], 4)
        options = spec.get("options", ["up", "down", "flat"])
        band = spec.get("flat_band")
        if band is None and "flat" in options:
            if not percent:
                r.error("direction.flat_band is required for series that are not index100")
                return None
            band = default_flat_band(steps, p["frequency"])
        if "flat" in options and abs(change) <= band:
            direction = "flat"
        elif change == 0:
            r.error("the series is unchanged at the horizon and 'flat' is not an option")
            return None
        else:
            direction = "up" if change > 0 else "down"
        unit = "%" if percent else ("pp" if p["unit"] in ("%", "% y/y") else p["unit"])
        if spec.get("expected") and spec["expected"] != direction:
            r.error(f"expected {spec['expected']} but the data says {direction} ({change:+g} {unit}): "
                    "fact-check the cutoff, the news and the direction")
        return {"direction": direction, "change": change, "unit": unit, "flat_band": band, "steps": steps}

    def check(self, spec: dict, value) -> str | None:
        options = spec.get("options", ["up", "down", "flat"])
        return None if value in options else f"response must be one of {options}"

    def score(self, spec: dict, value, truth) -> float:
        return 1.0 if value == truth else 0.0


RESPONSES = {"direction": DirectionResponse()}


# ---------------------------------------------------------------- truths

class NoTruth:
    """Day X: the outcome is shown in the reveal but not scored."""

    def resolve(self, spec: dict, outcome: dict | None):
        return None


class OutcomeTruth:
    """The realised outcome is the correct answer (e.g. a direction task that is not day X)."""

    def resolve(self, spec: dict, outcome: dict | None):
        return outcome["direction"] if outcome else None


TRUTHS = {"none": NoTruth(), "outcome": OutcomeTruth()}


# ---------------------------------------------------------------- reasons

ID_RE = re.compile(r"^[a-z0-9_]+$")


def validate_reasons(spec: dict, r: Report):
    boxes = spec.get("boxes") if isinstance(spec, dict) else None
    if not isinstance(boxes, list) or len(boxes) < 2:
        r.error("reasons.boxes must list at least 2 boxes")
        return
    if not 6 <= len(boxes) <= 8:
        r.warn(f"reasons: {len(boxes)} boxes (the spec suggests 6-8)")
    ids = [b.get("id") for b in boxes]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and ID_RE.match(i) for i in ids):
        r.error("reasons: box ids must be unique lowercase ids")
    weights = []
    for b in boxes:
        w = b.get("weight")
        if isinstance(w, bool) or not isinstance(w, (int, float)) or not -1 <= w <= 1:
            r.error(f"reasons: box {b.get('id')} weight must be from -1 to 1")
        else:
            weights.append(w)
        if not is_text(b.get("text")):
            r.error(f"reasons: box {b.get('id')} needs text")
        if not is_text(b.get("explain")):
            r.error(f"reasons: box {b.get('id')} needs explain (shown in the reveal)")
    if weights and max(weights) <= 0:
        r.error("reasons: at least one box needs a positive weight")
    pick = spec.get("pick") or {}
    lo, hi = pick.get("min"), pick.get("max")
    if not (isinstance(lo, int) and isinstance(hi, int) and 1 <= lo <= hi <= len(boxes)):
        r.error("reasons.pick needs integers 1 <= min <= max <= number of boxes")
    elif weights and sum(1 for w in weights if w > 0) < lo:
        r.warn("reasons: fewer positive boxes than pick.min, so nobody can score 1")


def public_reasons(spec: dict) -> dict:
    return {"pick": spec["pick"], "boxes": [{"id": b["id"], "text": b["text"]} for b in spec["boxes"]]}


def private_reasons(spec: dict) -> list[dict]:
    return [{"id": b["id"], "weight": float(b["weight"]), "explain": b["explain"]} for b in spec["boxes"]]


def score_reasons(boxes: list[dict], picked: list[str]) -> float:
    """Sum of the picked weights / best possible sum for the same number of boxes, clipped to 0-1."""
    if not picked:
        return 0.0
    weights = {b["id"]: b["weight"] for b in boxes}
    best = sum(sorted((max(w, 0.0) for w in weights.values()), reverse=True)[:len(picked)])
    if best <= 0:
        return 0.0
    return min(1.0, max(0.0, sum(weights[p] for p in picked) / best))
