"""Simulation core shared by the hard engine, the time machine and the sandbox
(docs/architecture.md, docs/market_sim.md). Household half: sim.household. Market half:
sim.market (path sources) and sim.portfolio (multi-asset holdings)."""
from .household import ACTIONS, ASSET_ACTIONS, Household, Scenario, metrics, run
from .market import KINDS, MarketPath, bootstrap, build_path, fictional, replay, synthetic, synthetic_returns
from .portfolio import portfolio_metrics, rebalance_trades, run_portfolio

__all__ = ["ACTIONS", "ASSET_ACTIONS", "Household", "Scenario", "metrics", "run", "KINDS", "MarketPath", "bootstrap", "build_path",
           "fictional", "replay", "synthetic", "synthetic_returns", "portfolio_metrics", "rebalance_trades",
           "run_portfolio"]
