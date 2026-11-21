"""The household half of the simulation core (docs/architecture.md, "The simulation core").

One month, in this order:
1. income arrives (0 in a job-loss month); essential costs (times the price level) and any
   shock are paid. The result is this month's `cash`, which may be negative;
2. the policy runs and returns actions: sell investments, pay card debt, save to the buffer,
   invest, rebalance. Each action is capped by what is available;
3. if cash is still negative, the buffer covers it, then the credit card;
4. positive cash left over is spent (what you do not assign, you spend);
5. interest and returns are applied: buffer rate, card rate, and each asset's market return.

Investments are holdings per asset (docs/market_sim.md). With one asset (S1) everything goes
into it. With a `target` mix (P4), `invest` buys in the target proportions, `sell_investments`
sells pro rata, and `rebalance` trades back to the target, paying `trade_fee` on traded money.

Everything is deterministic for the same inputs. Market returns come from sim.market.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ACTIONS = ("sell_investments", "pay_debt", "save_to_buffer", "invest", "rebalance")


@dataclass
class Household:
    income: float          # net pay per month
    costs: float           # essential costs per month at today's prices
    buffer: float = 0.0    # savings account
    invested: float | dict = 0.0   # one fund (a number) or {asset: value}
    card_debt: float = 0.0
    buffer_rate: float = 0.04      # per year
    card_rate: float = 0.20        # per year
    target: dict | None = None     # {asset: weight}, sums to 1; None = one fund
    trade_fee: float = 0.0         # share of traded money lost on rebalancing


@dataclass
class Scenario:
    months: int
    returns: list[float] | dict[str, list[float]]                   # per month; a list = the single fund
    job_loss: list[tuple[int, int]] = field(default_factory=list)   # (first month, length)
    shocks: dict[int, float] = field(default_factory=dict)          # month -> one-off cost
    price_rise: tuple[int, float] | None = None                      # (from month, +x)


def _unemployed(month: int, job_loss: list[tuple[int, int]]) -> bool:
    return any(start <= month < start + length for start, length in job_loss)


def run(h: Household, policy, sc: Scenario) -> list[dict]:
    """Simulate `sc.months` months. `policy(ctx)` returns [(action, amount), ...]. Returns one row
    per month; the household object is not changed."""
    returns = sc.returns if isinstance(sc.returns, dict) else {"fund": sc.returns}
    assets = list(returns)
    if isinstance(h.invested, dict):
        holdings = {a: float(h.invested.get(a, 0.0)) for a in assets}
    else:
        holdings = {a: 0.0 for a in assets}
        holdings[assets[0]] = float(h.invested)
    target = h.target or {assets[0]: 1.0}
    first = assets[0]
    buffer, debt = h.buffer, h.card_debt
    rows, contributed, debt_max = [], 0.0, debt
    peak, since_rebalance = sum(holdings.values()), 0
    for m in range(1, sc.months + 1):
        level = 1 + sc.price_rise[1] if sc.price_rise and m >= sc.price_rise[0] else 1.0
        costs = h.costs * level
        employed = not _unemployed(m, sc.job_loss)
        income = h.income if employed else 0.0
        shock = sc.shocks.get(m, 0.0)
        cash = income - costs - shock

        invested = sum(holdings.values())
        weight = holdings[first] / invested if invested else 0.0
        ctx = {"month": m, "income": income, "costs": costs, "cash": max(cash, 0.0), "shortfall": max(-cash, 0.0),
               "buffer": buffer, "buffer_months": buffer / costs, "invested": invested,
               "card_debt": debt, "employed": 1.0 if employed else 0.0,
               "shares_weight": weight, "drift": abs(weight - target.get(first, 0.0)),
               "drawdown": 1 - invested / peak if peak else 0.0, "months_since_rebalance": since_rebalance}
        done = []
        since_rebalance += 1
        for action, amount in policy(ctx):
            amount = max(0.0, float(amount))
            x = 0.0
            if action == "sell_investments":
                total = sum(holdings.values())
                x = min(amount, total)
                if total:
                    holdings = {a: v - x * v / total for a, v in holdings.items()}
                cash += x
            elif action == "pay_debt":
                x = min(amount, max(cash, 0.0), debt)
                debt -= x
                cash -= x
            elif action == "save_to_buffer":
                x = min(amount, max(cash, 0.0))
                buffer += x
                cash -= x
            elif action == "invest":
                x = min(amount, max(cash, 0.0))
                for a, w in target.items():
                    holdings[a] += x * w
                contributed += x
                cash -= x
            elif action == "rebalance":
                total = sum(holdings.values())
                trades = {a: total * target.get(a, 0.0) - v for a, v in holdings.items()}
                x = sum(abs(t) for t in trades.values()) / 2
                holdings = {a: v + trades[a] for a, v in holdings.items()}
                if x and h.trade_fee:
                    cost = 2 * x * h.trade_fee
                    holdings = {a: v - cost * target.get(a, 0.0) for a, v in holdings.items()}
                since_rebalance = 0
            else:
                raise ValueError(f"unknown action {action!r}")
            if x:
                done.append((action, round(x, 2)))

        from_buffer = from_card = 0.0
        if cash < 0:
            from_buffer = min(-cash, buffer)
            buffer -= from_buffer
            cash += from_buffer
        if cash < 0:
            from_card = -cash
            debt += from_card
            cash = 0.0
        spent = cash

        buffer *= 1 + h.buffer_rate / 12
        debt *= 1 + h.card_rate / 12
        holdings = {a: v * (1 + returns[a][m - 1]) for a, v in holdings.items()}
        invested = sum(holdings.values())
        peak = max(peak, invested)
        debt_max = max(debt_max, debt)
        rows.append({"month": m, "income": round(income, 2), "costs": round(costs, 2), "shock": round(shock, 2),
                     "actions": done, "from_buffer": round(from_buffer, 2), "from_card": round(from_card, 2),
                     "spent": round(spent, 2), "buffer": round(buffer, 2), "invested": round(invested, 2),
                     "holdings": {a: round(v, 2) for a, v in holdings.items()},
                     "weights": {a: round(v / invested, 4) if invested else 0.0 for a, v in holdings.items()},
                     "card_debt": round(debt, 2), "contributed": round(contributed, 2),
                     "card_debt_max": round(debt_max, 2)})
    return rows


def metrics(rows: list[dict]) -> dict:
    last = rows[-1]
    return {"card_debt_max": last["card_debt_max"], "card_debt_end": last["card_debt"],
            "min_buffer": min(r["buffer"] for r in rows), "contributed": last["contributed"],
            "net_worth_end": round(last["buffer"] + last["invested"] - last["card_debt"], 2)}
