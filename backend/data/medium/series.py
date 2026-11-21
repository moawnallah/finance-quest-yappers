"""Chart transforms for the medium engine. The series store itself is in the kernel
(backend/data/series_store.py); its names are re-exported here so existing imports keep working.
"""
from __future__ import annotations

from series_store import DataError, Series, SeriesStore, step_dates, synthetic_path  # noqa: F401


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
