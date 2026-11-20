"""The series table and chart transforms.

Data lives in two files (see docs/task_engines.md, "Data series and licences"):
- series/series.csv:  one row per observation: series_id, date, value, source, licence
- series/catalog.yaml: one entry per series_id: name, unit, frequency, source, licence,
                       display (may we show it?), and optional `synthetic` parameters.

A synthetic series (for example a fictional company, since single-company prices are not
licensed) has no rows in the CSV. It is generated in memory from its catalog parameters,
the same way every time.
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import random
from dataclasses import dataclass
from pathlib import Path

import yaml


class DataError(Exception):
    """A series is missing or unusable."""


@dataclass(frozen=True)
class Series:
    series_id: str
    dates: list[dt.date]
    values: list[float]
    meta: dict  # the catalog entry


class SeriesStore:
    def __init__(self, table: Path, catalog: Path):
        self.catalog: dict[str, dict] = (yaml.safe_load(catalog.read_text(encoding="utf-8")) or {}) if catalog.exists() else {}
        self._rows: dict[str, dict[dt.date, float]] = {}
        if table.exists():
            with table.open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    raw = (row.get("value") or "").strip()
                    if raw:
                        day = dt.date.fromisoformat(row["date"].strip()[:10])
                        self._rows.setdefault(row["series_id"].strip(), {})[day] = float(raw)

    def meta(self, series_id: str) -> dict | None:
        return self.catalog.get(series_id)

    def get(self, series_id: str) -> Series:
        meta = self.meta(series_id)
        if meta is None:
            raise DataError(f"series {series_id!r} is not in catalog.yaml")
        if meta.get("synthetic"):
            dates, values = synthetic_path(series_id, meta)
        else:
            rows = self._rows.get(series_id)
            if not rows:
                raise DataError(f"series {series_id!r} has no rows in series.csv")
            dates = sorted(rows)
            values = [rows[d] for d in dates]
        return Series(series_id, dates, values, meta)


# ---------------------------------------------------------------- transforms
# Each transform takes (dates, values, cutoff_index) and returns one value per date (None = undefined).

def _level(dates, values, cut):
    return list(values)


def _index100(dates, values, cut):
    base = values[cut]
    if base <= 0:
        raise DataError(f"cannot rebase to 100: value at cutoff is {base}")
    return [v / base * 100 for v in values]


def _yoy(dates, values, cut):
    """Change in % against the last observation at least one year earlier."""
    out, j = [], 0
    for i, d in enumerate(dates):
        year_ago = d.replace(year=d.year - 1) if not (d.month == 2 and d.day == 29) else d.replace(year=d.year - 1, day=28)
        while j + 1 <= i and dates[j + 1] <= year_ago:
            j += 1
        out.append((values[i] / values[j] - 1) * 100 if dates[j] <= year_ago and values[j] else None)
    return out


TRANSFORMS = {"level": _level, "index100": _index100, "yoy": _yoy}
# The unit a transform produces; None means "the series' own unit".
TRANSFORM_UNIT = {"level": None, "index100": "index (cutoff = 100)", "yoy": "% y/y"}


# ---------------------------------------------------------------- synthetic paths

def step_dates(anchor: dt.date, frequency: str, back: int, forward: int) -> list[dt.date]:
    """`back` observations before `anchor`, the anchor itself, and `forward` after it."""
    if frequency == "monthly":
        first = anchor.replace(day=1)

        def add(n: int) -> dt.date:
            m = first.month - 1 + n
            return dt.date(first.year + m // 12, m % 12 + 1, 1)

        return [add(k) for k in range(-back, forward + 1)]

    while anchor.weekday() >= 5:
        anchor -= dt.timedelta(days=1)
    before, after, d = [], [], anchor
    while len(before) < back:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            before.append(d)
    d = anchor
    while len(after) < forward:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            after.append(d)
    return before[::-1] + [anchor] + after


def synthetic_path(series_id: str, meta: dict) -> tuple[list[dt.date], list[float]]:
    """A random walk with a planted move: exactly `move` over `horizon` steps after `anchor`.

    mode multiplicative (default): `move` is a return (-0.08 = -8 %), `vol` a per-step return std.
    mode additive: `move` is a change in the series' unit (0.3 = +0.3), `vol` a per-step std.
    """
    p = meta["synthetic"]
    freq = meta.get("frequency", "daily")
    anchor = p["anchor"] if isinstance(p["anchor"], dt.date) else dt.date.fromisoformat(str(p["anchor"]))
    additive = p.get("mode", "multiplicative") == "additive"
    back, forward, horizon = p.get("back", 260), p.get("forward", 260), p.get("horizon", 5)
    vol = p.get("vol", (0.03 if additive else 0.012) if freq == "daily" else (0.15 if additive else 0.04))
    seed = p.get("seed", sum(map(ord, series_id)))

    rng = random.Random(seed)
    dates = step_dates(anchor, freq, back, forward)
    steps = [rng.gauss(0.0, vol) for _ in range(len(dates) - 1)]
    target = p.get("move", 0.0) if additive else math.log1p(p.get("move", 0.0))
    fix = (target - sum(steps[back:back + horizon])) / horizon
    for i in range(back, back + horizon):
        steps[i] += fix

    level, path = 0.0, [0.0]
    for s in steps:
        level += s
        path.append(level)
    start, offset = p.get("start", 100.0), path[back]
    if additive:
        values = [round(start + c - offset, 6) for c in path]
    else:
        values = [round(start * math.exp(c - offset), 6) for c in path]
    return dates, values
