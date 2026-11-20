"""The market half of the simulation core: where monthly returns come from.

Implemented so far: `synthetic_returns`, an illustrative model labelled as such in every task
that uses it. To come (docs/architecture.md): `replay` of a real series from the series store,
`bootstrap` of real history, and the `fictional` market with generated events for the sandbox.
"""
from __future__ import annotations

import random


def synthetic_returns(months: int, seed: int, mean: float = 0.005, sd: float = 0.04) -> list[float]:
    """Monthly returns of a broad share fund: normal with the given mean and standard deviation.
    Illustrative only; the task's `assumptions` say so on screen."""
    rng = random.Random(seed)
    return [rng.gauss(mean, sd) for _ in range(months)]
