# Hard engine: block programs on the simulation core

Readers:
- Yurii (engines);
- Mohamed (API);
- Michał (the Blockly screen);
- content authors writing hard tasks.

Purpose: how the hard engine works, what a task file contains, and what
goes in and out.

Status: first version, 2026-11-21.
- It runs the household half of the simulation core with one task, S1
  "Ania's buffer rule".
- The market half has only a synthetic return model so far.

Architecture: [architecture.md](architecture.md). Spec it implements:
[task_engines.md](task_engines.md), "Hard engine".

## How a submission is scored

1. **Check the program.** It must be built only from the task's palette
   and values, and stay within the block and depth limits. A failed check
   returns an error list; nothing runs.
2. **Compile** the JSON program into a policy. It is interpreted; user code
   never runs.
3. **Obligatory tests:** named scenarios with a check.
   - If any fails, the result is "not accepted", with the failing test's
     month-by-month story.
4. **Optional tests:** named scenarios, each with a probability. Each gets a
   metric:
   - 1 = never needed the card;
   - 0.5 = needed it but repaid it by the end;
   - 0 = still in debt.
5. **Points** = 51 + 49 × (probability-weighted share of the optional
   metrics). The attempt record stores `score` = points / 100 (0-1, like
   the other engines) and `points` (51-100).
6. **Futures:** the share of 200 random futures in which the rule never
   needed the card.
   - The futures are random job losses and shocks, with a fixed seed.
   - Shown as "in 182 of 200 futures you never needed the card".
   - Not part of the points.

Baseline bots are scored at build time and shipped in the question, so the
histogram has reference points before there are users.

## The month (sim/household.py)

1. **Money arrives and goes out.** Income arrives (0 in a job-loss month).
   Essential costs (times the price level) and any shock are paid. This
   gives the month's `cash`.
2. **The policy runs.** Its actions are:
   - `sell_investments`;
   - `pay_debt`;
   - `save_to_buffer`;
   - `invest`.

   Each action is capped by what is available.
3. **Shortfalls.** Still short: the buffer pays, then the credit card.
4. **Leftovers.** Cash left over is spent: what you do not assign, you
   spend.
5. **Interest and returns.** Buffer interest, card interest and the
   investment return are applied.

## The block language (hard/dsl.py)

```json
{"every_month": [
  {"block": "if_else",
   "if": {"block": "compare", "op": "<", "left": {"block": "var", "name": "buffer_months"}, "right": {"block": "number", "value": 3}},
   "then": [{"block": "save_to_buffer", "amount": {"block": "var", "name": "cash"}}],
   "else": [{"block": "invest", "amount": {"block": "var", "name": "cash"}}]}
]}
```

| Kind | Blocks |
|---|---|
| Statements | `if_else`, actions `save_to_buffer`, `invest`, `pay_debt`, `sell_investments` (each with an `amount`) |
| Conditions | `compare` (`<`, `>`), `and`, `or`, `not` |
| Numbers | `number`, `var`, `math` (`*`, `+`, `-`, `min`) |

**Values (`var`):**
- `cash`;
- `shortfall`;
- `buffer_months`;
- `buffer`;
- `costs`;
- `card_debt`;
- `invested`;
- `employed`;
- `month`.

Each block and value has an English sentence template in `BLOCKS` and
`VARS`. The question sends them with the palette, so the app can build the
Blockly toolbox from the data, for example "If months my buffer covers is
less than 3 then put money left this month PLN into my buffer otherwise
...".

## A task file (`hard:` in the node file)

See `backend/content/nodes/S1.yaml`.

| Field | Meaning |
|---|---|
| `id`, `level`, `content_version`, `author`, `reviewer`, `sources` | As for the other engines; `id` is `<node>.h<n>` |
| `brief`, `editorial` | Text before and after |
| `palette`, `vars`, `limits`, `starter_program` | What the user can build with |
| `household` | `income`, `costs`, `buffer`, optional `invested`, `card_debt`, `buffer_rate`, `card_rate` |
| `world` | `months`; `market: {kind: synthetic, seed, mean, sd}` |
| `assumptions` | Shown on screen; every illustrative number is listed |
| `obligatory` | `{name, override, check}`. `check` is `no_card_debt`, `contributed_at_least` or `net_worth_at_least` |
| `optional` | `{name, probability, override}` |
| `override` | `job_loss: [[month, length]]`, `shocks: {month: amount}`, `price_rise: [month, +x]` |
| `futures` | `n`, `seed`, `job_loss_per_month`, `job_loss_months: [min, max]`, `shock_per_month`, `shock_amount: [min, max]` |
| `reference_program`, `known_bad_programs` (with `fails`), `baseline_bots` | The golden checks and the histogram bots |

**The build** (`python -m hard.build --strict`, or `python build.py
--strict` for every engine) runs the golden checks:
- the reference must be accepted;
- each known-bad program must fail the test it names.

A task that fails the golden checks is left out.

## API

```python
from hard import load_records, question_view, reveal_view, score
rec = load_records()["s1.h1"]
question_view(rec)          # GET /tasks/s1.h1: brief, palette with templates, values, limits,
                            #   starter program, household, assumptions, obligatory test names, bots
score(rec, program)         # POST /answers: accepted, points, score, obligatory, optional, story, futures
reveal_view(rec)            # after the answer: reference program, editorial, optional events
```

The question never contains:
- the reference program;
- the optional events;
- the editorial;
- `meta`.

A test checks this.

## S1 result (build 2026-11-21)

| Program | Accepted | Points | Futures without the card |
|---|---|---|---|
| Reference: pay card debt, then a 3-month buffer, then invest | yes | 97 | 182 / 200 |
| Bot: 2-month buffer, then invest | yes | 91 | 176 / 200 |
| Bot: 6-month buffer, then invest | yes | 100 | 189 / 200 |
| Bot: invest everything | no: card used in the job-loss test | - | - |

**Note:** the points measure resilience only. A bigger buffer always scores
at least as well, as long as it still invests 15,000 PLN. A second
objective (for example real wealth at the end) would make the trade-off
visible; decide before adding it.

## Not yet

- **Market half:** `replay` of a real monthly series, `bootstrap` of real
  history, and the `fictional` market for the sandbox. P4 (rebalancing)
  needs `replay` plus a holdings model with more than one asset.
- **A JSON schema** for `output/hard_tasks.json`.
- **The `Engine` protocol** in `common.py`, and an API registry.
