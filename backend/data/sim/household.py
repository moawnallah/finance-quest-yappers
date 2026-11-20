"""The household half of the simulation core (docs/architecture.md, "The simulation core").

One month, in this order:
1. income arrives (0 in a job-loss month); essential costs (times the price level) and any
   shock are paid. The result is this month's `cash`, which may be negative;
2. the policy runs and returns actions: sell investments, pay card debt, save to the buffer,
   invest. Each action is capped by what is available;
3. if cash is still negative, the buffer covers it, then the credit card;
4. positive cash left over is spent (what you do not assign, you spend);
5. interest and returns are applied: buffer rate, card rate, the market return on investments.

Everything is deterministic for the same inputs. Market returns come from sim.market.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ACTIONS = ("sell_investments", "pay_debt", "save_to_buffer", "invest")


@dataclass
class Household:
    income: float          # net pay per month
    costs: float           # essential costs per month at today's prices
    buffer: float = 0.0    # savings account
    invested: float = 0.0  # market value of investments
    card_debt: float = 0.0
    buffer_rate: float = 0.04   # per year
    card_rate: float = 0.20     # per year


@dataclass
class Scenario:
    months: int
    returns: list[float]                                   # one market return per month
    job_loss: list[tuple[int, int]] = field(default_factory=list)   # (first month, length)
    shocks: dict[int, float] = field(default_factory=dict)          # month -> one-off cost
    price_rise: tuple[int, float] | None = None                      # (from month, +x)


def _unemployed(month: int, job_loss: list[tuple[int, int]]) -> bool:
    return any(start <= month < start + length for start, length in job_loss)


def run(h: Household, policy, sc: Scenario) -> list[dict]:
    """Simulate `sc.months` months. `policy(ctx)` returns [(action, amount), ...]. Returns one row
    per month; the household object is not changed."""
    buffer, invested, debt = h.buffer, h.invested, h.card_debt
    rows, contributed, debt_max = [], 0.0, debt
    for m in range(1, sc.months + 1):
        level = 1 + sc.price_rise[1] if sc.price_rise and m >= sc.price_rise[0] else 1.0
        costs = h.costs * level
        employed = not _unemployed(m, sc.job_loss)
        income = h.income if employed else 0.0
        shock = sc.shocks.get(m, 0.0)
        cash = income - costs - shock

        ctx = {"month": m, "income": income, "costs": costs, "cash": max(cash, 0.0), "shortfall": max(-cash, 0.0),
               "buffer": buffer, "buffer_months": buffer / costs, "invested": invested,
               "card_debt": debt, "employed": 1.0 if employed else 0.0}
        done = []
        for action, amount in policy(ctx):
            amount = max(0.0, float(amount))
            if action == "sell_investments":
                x = min(amount, invested)
                invested -= x
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
                invested += x
                contributed += x
                cash -= x
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
        invested *= 1 + sc.returns[m - 1]
        debt_max = max(debt_max, debt)
        rows.append({"month": m, "income": round(income, 2), "costs": round(costs, 2), "shock": round(shock, 2),
                     "actions": done, "from_buffer": round(from_buffer, 2), "from_card": round(from_card, 2),
                     "spent": round(spent, 2), "buffer": round(buffer, 2), "invested": round(invested, 2),
                     "card_debt": round(debt, 2), "contributed": round(contributed, 2),
                     "card_debt_max": round(debt_max, 2)})
    return rows


def metrics(rows: list[dict]) -> dict:
    last = rows[-1]
    return {"card_debt_max": last["card_debt_max"], "card_debt_end": last["card_debt"],
            "min_buffer": min(r["buffer"] for r in rows), "contributed": last["contributed"],
            "net_worth_end": round(last["buffer"] + last["invested"] - last["card_debt"], 2)}
