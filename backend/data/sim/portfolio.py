"""A multi-asset portfolio run on a MarketPath (docs/market_sim.md). Used by the time machine and
the sandbox now, and by multi-asset hard tasks (P4 rebalancing) next.

A policy is called at each checkpoint with the current state and returns target weights or
trades; between checkpoints the holdings just follow the market.
"""
from __future__ import annotations

from .market import MarketPath


def rebalance_trades(holdings: dict[str, float], target: dict[str, float]) -> dict[str, float]:
    """Trades (asset -> + buy / - sell, in money) that bring holdings to the target weights.
    Weights must be non-negative and sum to 1; missing assets get weight 0."""
    if any(w < 0 for w in target.values()) or abs(sum(target.values()) - 1) > 1e-9:
        raise ValueError("target weights must be >= 0 and sum to 1")
    total = sum(holdings.values())
    assets = set(holdings) | set(target)
    return {a: total * target.get(a, 0.0) - holdings.get(a, 0.0) for a in sorted(assets)}


def run_portfolio(path: MarketPath, start: dict[str, float], policy=None, every: int = 1, fee: float = 0.0) -> list[dict]:
    """Hold `start` (money per asset) through the path. Every `every` steps (before the step's
    return) `policy(ctx)` may return {"target": {asset: weight}} or {"trades": {asset: money}}.
    `fee` is a proportional cost on traded money. Returns one row per step."""
    unknown = set(start) - set(path.assets)
    if unknown:
        raise ValueError(f"assets not on the path: {sorted(unknown)}")
    holdings = {a: float(start.get(a, 0.0)) for a in path.assets}
    peak, rows = sum(holdings.values()), []
    for step in range(path.steps):
        traded = 0.0
        if policy is not None and step % every == 0:
            total = sum(holdings.values())
            ctx = {"step": step + 1, "value": total, "holdings": dict(holdings),
                   "weights": {a: (v / total if total else 0.0) for a, v in holdings.items()},
                   "drawdown": 1 - total / peak if peak else 0.0,
                   "date": path.dates[step] if path.dates else None}
            decision = policy(ctx) or {}
            trades = rebalance_trades(holdings, decision["target"]) if "target" in decision else decision.get("trades", {})
            for a, x in trades.items():
                if a not in holdings:
                    raise ValueError(f"unknown asset {a!r}")
                x = max(x, -holdings[a])          # cannot sell more than held
                holdings[a] += x
                traded += abs(x)
            if traded and fee:
                total_after = sum(holdings.values())
                cost = traded * fee
                holdings = {a: v - cost * v / total_after for a, v in holdings.items()} if total_after else holdings
        holdings = {a: v * (1 + path.returns[a][step]) for a, v in holdings.items()}
        value = sum(holdings.values())
        peak = max(peak, value)
        rows.append({"step": step + 1, "date": path.dates[step] if path.dates else None,
                     "value": round(value, 2), "holdings": {a: round(v, 2) for a, v in holdings.items()},
                     "drawdown": round(1 - value / peak, 4) if peak else 0.0, "traded": round(traded, 2)})
    return rows


def portfolio_metrics(rows: list[dict], start_value: float) -> dict:
    end = rows[-1]["value"]
    return {"end_value": end, "total_return": round(end / start_value - 1, 4) if start_value else None,
            "max_drawdown": max(r["drawdown"] for r in rows), "traded": round(sum(r["traded"] for r in rows), 2)}
