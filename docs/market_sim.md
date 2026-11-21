# Market half of the simulation core

Readers:
- whoever builds the time machine, the sandbox or a multi-asset hard task
  (P4);
- Yurii (data);
- Mohamed (API).

Purpose: what `sim/market.py` and `sim/portfolio.py` provide, and how each
feature uses them.

Status: first version, 2026-11-21.
- Implemented and tested: all four path sources and the portfolio.
- Real data: none in `series.csv` yet, so replay and bootstrap are tested on
  small tables built in the tests.

Architecture: [architecture.md](architecture.md).

## MarketPath

Every source returns one `MarketPath`:

| Field | Meaning |
|---|---|
| `source` | `synthetic`, `replay`, `bootstrap` or `fictional` |
| `returns` | `{asset: [return per step]}`, all the same length (`steps`) |
| `labels` | `{asset: display name}`, e.g. fictional "CrocoTech" |
| `events` | `[{step, asset, shock, headline}]` (fictional market) |
| `regimes` | `["calm" / "stress" per step]` (fictional market) |
| `dates` | the end date of each step (replay only) |
| `attribution` | `[{asset, series_id, source, licence}]` for real data |
| `synthetic` | `false` only when every return is real data; the app must label anything else |

## The four sources

`build_path(spec, steps, seed, store)` picks the source from
`spec["kind"]`. `store` is the kernel's series store
(`backend/data/series_store.py`).

| Kind | What it does | Spec | Used by |
|---|---|---|---|
| `synthetic` | Independent normal returns per asset; illustrative | `{kind, asset or assets: {key: {mean, sd}}, seed}` | S1 hard task today |
| `replay` | One real path: returns of the level series from `start`, on their common dates | `{kind, series: {asset: series_id}, start, labels}` | Time machine, P4, day-X episodes |
| `bootstrap` | Blocks of real history drawn at random; the **same rows for every asset**, so their correlation is kept | `{kind, series, block, seed}` | Futures for hard tasks once data exists |
| `fictional` | Our fictional market: a calm/stress regime chain drives a common factor; each asset is `alpha + beta × factor + noise`; events add shocks and headlines | below | Sandbox |

**Fictional market spec** (sandbox):

```yaml
kind: fictional
seed: 7                       # the same seed gives the same market, so friends can play the same one
regimes:
  calm:   {mean: 0.01, sd: 0.02}
  stress: {mean: -0.03, sd: 0.06}
  calm_to_stress: 0.1         # per step
  stress_to_calm: 0.3
assets:
  crocotech: {label: CrocoTech, beta: 1.4, noise: 0.03}
  safebond:  {label: SafeBond, beta: 0.1, noise: 0.005}
events:
  - {asset: crocotech, probability: 0.05, shock: -0.25, headline: "CrocoTech loses its CEO"}
```

Calibration is open. The regime means and volatilities should be fitted on
real history (the OECD index once it is in the store) so that the fictional
market behaves like a market. Until then, label it "fictional,
illustrative".

## Portfolio (`sim/portfolio.py`)

- `run_portfolio(path, start, policy, every, fee)`:
  - holds money per asset through the path;
  - every `every` steps, `policy(ctx)` may return
    `{"target": {asset: weight}}` or `{"trades": {asset: money}}`;
  - `ctx` has `step`, `value`, `holdings`, `weights`, `drawdown` and
    `date`;
  - returns one row per step: value, holdings, drawdown, traded.
- `rebalance_trades(holdings, target)`: the trades that reach the target
  weights; they sum to zero.
- `portfolio_metrics(rows, start_value)`: end value, total return, maximum
  drawdown, money traded.

## How each feature uses it

| Feature | Path | Portfolio | Scoring |
|---|---|---|---|
| Hard tasks | `world.market` in the task: any kind. S1 uses one asset as its fund; P4 holds shares and bonds | the household ledger holds per-asset investments, with a target mix and a `rebalance` block (done 2026-11-21) | 51-100 resilience and a growth index (docs/hard_engine.md) |
| **Time machine** | `replay` of an episode (2008, March 2020, 2022) with checkpoints | the user's choices at each checkpoint become `trades` or `target` | none; show the result next to "held" and "sold at the bottom" |
| **Sandbox** | `fictional` with a shared seed per week | the user's portfolio | none, or a weekly challenge on the same seed. No money, prizes or exchangeable points |
| P4 hard task | synthetic today; `replay` (2020) and `bootstrap` once the data is in | the rebalancing rule as a block program | the hard engine's tests |

**Switching P4 to real data** is one change in `P4.yaml`, once the series
are in the store:

```yaml
world:
  months: 36
  market: {kind: bootstrap, series: {shares: oecd_pl_share_prices, bonds: pl_bond_index}, block: 12, seed: 2026112102}
```

The series ids are examples; they must match `catalog.yaml`.

## Data needed

These series go into `series/series.csv` and `catalog.yaml`, with the
licences checked (docs/task_engines.md):

| Asset | Series | Source |
|---|---|---|
| Polish shares (price index) | monthly, 2005- | OECD share prices, Poland (FRED SPASTT01PLM661N) |
| Polish bonds (approximation) | the 10-year yield, converted to an approximate monthly return | OECD long-term interest rate, Poland |
| Inflation | CPI y/y, monthly | GUS |
| US shares, bonds, bills | yearly, 1928- | Damodaran (attribution) |

The time machine needs a monthly equity series. That is the first series
to load.
