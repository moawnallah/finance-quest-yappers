"""The household half of the simulation core (docs/architecture.md, "The simulation core").

One month, in this order:
1. income arrives (0 in a job-loss month), plus any irregular extra income; essential costs
   (times the price level), any shock, any yearly bill not covered by the bills pot, and the
   card's minimum payment are paid. The result is this month's `cash`, which may be negative;
2. the policy runs and returns actions: sell investments, pay card debt, save to the buffer or
   the bills pot, invest, buy or sell one asset, rebalance. Each action is capped by what is
   available;
3. every 12th month, tax on the year's realised gains is paid (only if `tax_on_gains` is set);
4. if cash is still negative, the buffer covers it, then the credit card;
5. positive cash left over is spent (what you do not assign, you spend);
6. interest and returns are applied: buffer rate, card rate, and each asset's market return.

Investments are holdings per asset (docs/market_sim.md). With one asset (S1) everything goes
into it. With a `target` mix (P4), `invest` buys in the target proportions, `sell_investments`
sells pro rata, and `rebalance` trades back to the target, paying `trade_fee` on traded money.

The fields after `trade_fee` are optional mechanisms (docs/hard_engine.md, "Next version"). Each
is off by default, so tasks that do not set them behave exactly as before; a regression test
holds the tasks frozen on 2026-11-21 to their results.

Everything is deterministic for the same inputs. Market returns come from sim.market.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ACTIONS = ("sell_investments", "pay_debt", "save_to_buffer", "invest", "rebalance",
           "invest_in", "sell", "save_to_pot")
ASSET_ACTIONS = ("invest_in", "sell")


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
    # Optional mechanisms, off by default:
    bills: list = field(default_factory=list)      # [{name, amount, month, every}]: paid from the pot first
    pot: float = 0.0                               # bills pot at the start
    card_min_payment: float = 0.0                  # share of the card debt paid automatically each month
    sell_fee: dict = field(default_factory=dict)   # {asset: share of the sale}, e.g. a bond's early-sale fee
    broker_fee: dict | None = None                 # {rate, min}: every buy or sell leg pays max(rate * leg, min)
    glide: dict | None = None                      # {asset, from, to}: that asset's target moves in a straight line
    tax_on_gains: float = 0.0                      # tax on the year's net realised gains, paid every 12th month


@dataclass
class Scenario:
    months: int
    returns: list[float] | dict[str, list[float]]                   # per month; a list = the single fund
    job_loss: list[tuple[int, int]] = field(default_factory=list)   # (first month, length)
    shocks: dict[int, float] = field(default_factory=dict)          # month -> one-off cost
    price_rise: tuple[int, float] | None = None                      # (from month, +x)
    extra_income: list[float] = field(default_factory=list)          # per month, on top of income (if employed)


def _unemployed(month: int, job_loss: list[tuple[int, int]]) -> bool:
    return any(start <= month < start + length for start, length in job_loss)


def _bill_due(bills: list, month: int) -> float:
    total = 0.0
    for b in bills:
        every = b.get("every", 12)
        if month == b["month"] or (every and month > b["month"] and (month - b["month"]) % every == 0):
            total += b["amount"]
    return total


def _next_bill(bills: list, month: int) -> tuple[float, int]:
    """(amount, months until it is due), looking ahead from the next month; (0, 0) if none."""
    horizon = max([b.get("every", 12) or 0 for b in bills] + [b["month"] for b in bills] + [0])
    for d in range(1, horizon + 1):
        due = _bill_due(bills, month + d)
        if due:
            return due, d
    return 0.0, 0


def _target(h: Household, base: dict, month: int, months: int) -> dict:
    if not h.glide:
        return base
    a = h.glide["asset"]
    w = h.glide["from"] + (h.glide["to"] - h.glide["from"]) * (month - 1) / max(months - 1, 1)
    rest = 1 - base.get(a, 0.0)
    return {k: w if k == a else (v / rest * (1 - w) if rest else 0.0) for k, v in base.items()}


def _fee(h: Household, leg: float, asset: str | None = None, selling: bool = False) -> float:
    if leg <= 0:
        return 0.0
    fee = 0.0
    if h.broker_fee:
        fee += max(leg * h.broker_fee.get("rate", 0.0), h.broker_fee.get("min", 0.0))
    if selling:
        fee += leg * h.sell_fee.get(asset, 0.0)
    return fee


def run(h: Household, policy, sc: Scenario) -> list[dict]:
    """Simulate `sc.months` months. `policy(ctx)` returns [(action, amount), ...] or, for
    `invest_in` and `sell`, (action, amount, asset). `ctx["memory"]` is a dict that lives for the
    whole run (the program's own variables). Returns one row per month; `h` is not changed."""
    returns = sc.returns if isinstance(sc.returns, dict) else {"fund": sc.returns}
    assets = list(returns)
    if isinstance(h.invested, dict):
        holdings = {a: float(h.invested.get(a, 0.0)) for a in assets}
    else:
        holdings = {a: 0.0 for a in assets}
        holdings[assets[0]] = float(h.invested)
    base_target = h.target or {assets[0]: 1.0}
    first = assets[0]
    buffer, debt, pot = h.buffer, h.card_debt, h.pot
    basis = dict(holdings)          # cost basis per asset: what was paid for what is still held
    gains_this_year = 0.0
    memory: dict[str, float] = {}
    rows, contributed, debt_max = [], 0.0, debt
    peak, since_rebalance = sum(holdings.values()), 0

    def realise(asset: str, amount: float, fee: float) -> None:
        nonlocal gains_this_year
        value = holdings[asset]
        part = basis[asset] * amount / value if value else 0.0
        basis[asset] -= part
        gains_this_year += amount - fee - part

    for m in range(1, sc.months + 1):
        level = 1 + sc.price_rise[1] if sc.price_rise and m >= sc.price_rise[0] else 1.0
        costs = h.costs * level
        employed = not _unemployed(m, sc.job_loss)
        extra = sc.extra_income[m - 1] if m <= len(sc.extra_income) else 0.0
        income = (h.income + extra if extra else h.income) if employed else 0.0
        shock = sc.shocks.get(m, 0.0)
        cash = income - costs - shock
        bill = _bill_due(h.bills, m) if h.bills else 0.0
        if bill:
            from_pot = min(pot, bill)
            pot -= from_pot
            cash -= bill - from_pot
        if h.card_min_payment and debt > 0:
            minimum = debt * h.card_min_payment
            debt -= minimum
            cash -= minimum

        target = _target(h, base_target, m, sc.months)
        invested = sum(holdings.values())
        weight = holdings[first] / invested if invested else 0.0
        next_bill, months_to_bill = _next_bill(h.bills, m) if h.bills else (0.0, 0)
        ctx = {"month": m, "income": income, "costs": costs, "cash": max(cash, 0.0), "shortfall": max(-cash, 0.0),
               "buffer": buffer, "buffer_months": buffer / costs, "invested": invested,
               "card_debt": debt, "employed": 1.0 if employed else 0.0,
               "shares_weight": weight, "drift": abs(weight - target.get(first, 0.0)),
               "drawdown": 1 - invested / peak if peak else 0.0, "months_since_rebalance": since_rebalance,
               "pot": pot, "next_bill": next_bill, "months_to_next_bill": months_to_bill,
               "target_shares": target.get(first, 0.0), "years_to_goal": (sc.months - m + 1) / 12,
               "tax_due_this_year": h.tax_on_gains * max(gains_this_year, 0.0), "memory": memory}
        done = []
        since_rebalance += 1
        for action, amount, *rest in policy(ctx):
            asset = rest[0] if rest else None
            amount = max(0.0, float(amount))
            x = 0.0
            if action == "sell_investments":
                total = sum(holdings.values())
                x = min(amount, total)
                fees = 0.0
                if total:
                    for a, v in list(holdings.items()):
                        part = x * v / total
                        fee = _fee(h, part, a, selling=True)
                        realise(a, part, fee)
                        holdings[a] = v - part
                        fees += fee
                cash += x - fees
            elif action == "pay_debt":
                x = min(amount, max(cash, 0.0), debt)
                debt -= x
                cash -= x
            elif action == "save_to_buffer":
                x = min(amount, max(cash, 0.0))
                buffer += x
                cash -= x
            elif action == "save_to_pot":
                x = min(amount, max(cash, 0.0))
                pot += x
                cash -= x
            elif action == "invest":
                x = min(amount, max(cash, 0.0))
                for a, w in target.items():
                    holdings[a] += x * w - _fee(h, x * w)
                    basis[a] += x * w
                contributed += x
                cash -= x
            elif action == "invest_in":
                x = min(amount, max(cash, 0.0))
                holdings[asset] += x - _fee(h, x)
                basis[asset] += x
                contributed += x
                cash -= x
            elif action == "sell":
                x = min(amount, holdings[asset])
                fee = _fee(h, x, asset, selling=True)
                realise(asset, x, fee)
                holdings[asset] -= x
                cash += x - fee
            elif action == "rebalance":
                total = sum(holdings.values())
                trades = {a: total * target.get(a, 0.0) - v for a, v in holdings.items()}
                x = sum(abs(t) for t in trades.values()) / 2
                leg_fees = 0.0
                for a, t in trades.items():
                    fee = _fee(h, abs(t), a, selling=t < 0)
                    if t < 0:
                        realise(a, -t, fee)
                    else:
                        basis[a] += t
                    leg_fees += fee
                holdings = {a: v + trades[a] for a, v in holdings.items()}
                if x and h.trade_fee:
                    cost = 2 * x * h.trade_fee
                    holdings = {a: v - cost * target.get(a, 0.0) for a, v in holdings.items()}
                if leg_fees:
                    holdings = {a: v - leg_fees * target.get(a, 0.0) for a, v in holdings.items()}
                since_rebalance = 0
            else:
                raise ValueError(f"unknown action {action!r}")
            if x:
                done.append((action, round(x, 2)) if asset is None else (action, round(x, 2), asset))

        tax = 0.0
        if h.tax_on_gains and m % 12 == 0:
            tax = h.tax_on_gains * max(gains_this_year, 0.0)
            cash -= tax
            gains_this_year = 0.0

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
        row = {"month": m, "income": round(income, 2), "costs": round(costs, 2), "shock": round(shock, 2),
               "actions": done, "from_buffer": round(from_buffer, 2), "from_card": round(from_card, 2),
               "spent": round(spent, 2), "buffer": round(buffer, 2), "invested": round(invested, 2),
               "holdings": {a: round(v, 2) for a, v in holdings.items()},
               "weights": {a: round(v / invested, 4) if invested else 0.0 for a, v in holdings.items()},
               "card_debt": round(debt, 2), "contributed": round(contributed, 2),
               "card_debt_max": round(debt_max, 2)}
        # Keys for optional mechanisms appear only when the mechanism is on (the frozen tasks' rows stay identical).
        if h.bills:
            row.update(bill=round(bill, 2), pot=round(pot, 2))
        if h.glide:
            row["target"] = round(target.get(first, 0.0), 4)
        if h.tax_on_gains:
            row["tax"] = round(tax, 2)
        rows.append(row)
    return rows


def metrics(rows: list[dict]) -> dict:
    last = rows[-1]
    return {"card_debt_max": last["card_debt_max"], "card_debt_end": last["card_debt"],
            "min_buffer": min(r["buffer"] for r in rows), "contributed": last["contributed"],
            "borrowed": round(sum(r["from_card"] for r in rows), 2),
            "net_worth_end": round(last["buffer"] + last["invested"] + last.get("pot", 0.0) - last["card_debt"], 2)}
