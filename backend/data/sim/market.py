"""The market half of the simulation core (docs/market_sim.md): where returns come from.

Every source returns a MarketPath: per-step returns for each asset, plus labels, events and,
for real data, dates and attribution. Four sources:
- synthetic: independent normal returns per asset; illustrative, labelled synthetic;
- replay:    one real path from the series store, from a start date (time machine, P4);
- bootstrap: blocks of real history drawn at random, the same rows for all assets, so the
             correlation between assets is kept (futures for hard tasks);
- fictional: our fictional market for the sandbox: a calm/stress regime chain drives a
             common factor, each asset has its own beta and noise, and generated events
             ("Company X loses its CEO") add shocks and headlines. Labelled fictional.
`build_path(spec, steps, seed, store)` picks the source from spec["kind"].
"""
from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field

KINDS = ("synthetic", "replay", "bootstrap", "fictional")


@dataclass
class MarketPath:
    source: str
    returns: dict[str, list[float]]          # asset -> one return per step
    labels: dict[str, str] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)   # {step, asset, shock, headline}
    dates: list[str] | None = None           # replay only: the date of each step's end
    attribution: list[dict] = field(default_factory=list)
    synthetic: bool = True                   # True unless every return is real data
    regimes: list[str] | None = None         # fictional only: "calm" / "stress" per step

    @property
    def assets(self) -> list[str]:
        return list(self.returns)

    @property
    def steps(self) -> int:
        return len(next(iter(self.returns.values()))) if self.returns else 0


# ---------------------------------------------------------------- synthetic

def synthetic_returns(months: int, seed: int, mean: float = 0.005, sd: float = 0.04) -> list[float]:
    """One asset's normal returns. Kept for callers that need a single list."""
    rng = random.Random(seed)
    return [rng.gauss(mean, sd) for _ in range(months)]


def synthetic(assets: dict[str, dict], steps: int, seed: int) -> MarketPath:
    """assets: {key: {mean, sd, label?}}. Independent normal returns, one seed per asset."""
    returns = {a: synthetic_returns(steps, seed + i, p.get("mean", 0.005), p.get("sd", 0.04))
               for i, (a, p) in enumerate(sorted(assets.items()))}
    return MarketPath("synthetic", returns, {a: p.get("label", a) for a, p in assets.items()})


# ---------------------------------------------------------------- real data

def _levels(store, series_id: str) -> tuple[list[dt.date], list[float], dict]:
    s = store.get(series_id)
    return s.dates, s.values, s.meta


def aligned_returns(store, series: dict[str, str]) -> tuple[list[dt.date], dict[str, list[float]], list[dict]]:
    """Returns of several level series on their common dates. series: {asset: series_id}.
    The first common date has no return, so the result starts at the second."""
    data = {a: _levels(store, sid) for a, sid in series.items()}
    common = sorted(set.intersection(*(set(d) for d, _, _ in data.values())))
    if len(common) < 2:
        raise ValueError(f"series {sorted(series.values())} have fewer than 2 common dates")
    returns = {}
    for a, (dates, values, _) in data.items():
        lookup = dict(zip(dates, values))
        lv = [lookup[d] for d in common]
        returns[a] = [lv[i] / lv[i - 1] - 1 for i in range(1, len(lv))]
    attribution = [{"asset": a, "series_id": series[a], "source": m.get("source"), "licence": m.get("licence")}
                   for a, (_, _, m) in data.items()]
    return common[1:], returns, attribution


def replay(store, series: dict[str, str], start: str | dt.date, steps: int, labels: dict | None = None) -> MarketPath:
    """A real path of `steps` returns beginning after `start` (the first return is start -> next date)."""
    dates, returns, attribution = aligned_returns(store, series)
    start = start if isinstance(start, dt.date) else dt.date.fromisoformat(str(start))
    first = next((i for i, d in enumerate(dates) if d > start), None)
    if first is None or first + steps > len(dates):
        raise ValueError(f"not enough data after {start} for {steps} steps")
    synthetic_any = any(store.get(sid).meta.get("synthetic") for sid in series.values())
    return MarketPath("replay", {a: r[first:first + steps] for a, r in returns.items()}, labels or {},
                      dates=[d.isoformat() for d in dates[first:first + steps]], attribution=attribution,
                      synthetic=synthetic_any)


def bootstrap(history: dict[str, list[float]], steps: int, block: int, seed: int, labels: dict | None = None) -> MarketPath:
    """Draw blocks of `block` consecutive rows of history; the same rows for every asset."""
    n = len(next(iter(history.values())))
    if any(len(v) != n for v in history.values()):
        raise ValueError("bootstrap history must have the same length for every asset")
    if block < 1 or block > n:
        raise ValueError(f"block must be between 1 and {n}")
    rng = random.Random(seed)
    rows: list[int] = []
    while len(rows) < steps:
        start = rng.randrange(0, n - block + 1)
        rows.extend(range(start, start + block))
    rows = rows[:steps]
    return MarketPath("bootstrap", {a: [v[i] for i in rows] for a, v in history.items()}, labels or {}, synthetic=False)


# ---------------------------------------------------------------- fictional market (sandbox)

def fictional(spec: dict, steps: int, seed: int) -> MarketPath:
    """spec:
      regimes: {calm: {mean, sd}, stress: {mean, sd}, calm_to_stress: p, stress_to_calm: p}
      assets:  {key: {label, beta, alpha, noise}}          # r = alpha + beta * factor + N(0, noise)
      events:  [{asset, probability, shock, headline}]     # per step; shock added to that asset
    """
    rng = random.Random(seed)
    reg = spec["regimes"]
    state, regimes = "calm", []
    returns: dict[str, list[float]] = {a: [] for a in spec["assets"]}
    events = []
    for step in range(1, steps + 1):
        if state == "calm" and rng.random() < reg["calm_to_stress"]:
            state = "stress"
        elif state == "stress" and rng.random() < reg["stress_to_calm"]:
            state = "calm"
        regimes.append(state)
        factor = rng.gauss(reg[state]["mean"], reg[state]["sd"])
        shocks: dict[str, float] = {}
        for e in spec.get("events", []):
            if rng.random() < e["probability"]:
                shocks[e["asset"]] = shocks.get(e["asset"], 0.0) + e["shock"]
                events.append({"step": step, "asset": e["asset"], "shock": e["shock"], "headline": e["headline"]})
        for a, p in spec["assets"].items():
            r = p.get("alpha", 0.0) + p.get("beta", 1.0) * factor + rng.gauss(0, p.get("noise", 0.02))
            returns[a].append(max(-0.95, r + shocks.get(a, 0.0)))
    return MarketPath("fictional", returns, {a: p.get("label", a) for a, p in spec["assets"].items()}, events,
                      regimes=regimes)


# ---------------------------------------------------------------- one entry point

def build_path(spec: dict, steps: int, seed: int = 0, store=None) -> MarketPath:
    """spec["kind"] in KINDS. replay/bootstrap need `store` (series_store.SeriesStore)."""
    kind = spec.get("kind", "synthetic")
    if kind == "synthetic":
        assets = spec.get("assets") or {spec.get("asset", "shares"): {"mean": spec.get("mean", 0.005), "sd": spec.get("sd", 0.04)}}
        return synthetic(assets, steps, spec.get("seed", 1) + seed)
    if kind == "replay":
        return replay(store, spec["series"], spec["start"], steps, spec.get("labels"))
    if kind == "bootstrap":
        _, history, attribution = aligned_returns(store, spec["series"])
        path = bootstrap(history, steps, spec.get("block", 12), spec.get("seed", 1) + seed, spec.get("labels"))
        path.attribution = attribution
        return path
    if kind == "fictional":
        return fictional(spec, steps, spec.get("seed", 1) + seed)
    raise ValueError(f"market kind {kind!r}: use one of {KINDS}")
