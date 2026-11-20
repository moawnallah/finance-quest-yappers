"""Simulation core shared by the hard engine and, later, the time machine and the sandbox
(docs/architecture.md). Household half: sim.household. Market half: sim.market."""
from .household import ACTIONS, Household, Scenario, metrics, run
from .market import synthetic_returns

__all__ = ["ACTIONS", "Household", "Scenario", "metrics", "run", "synthetic_returns"]
