# Hard engine: block programs on the simulation core

Readers:
- Yurii (engines);
- Mohamed (API);
- Michał (the Blockly screen);
- content authors writing hard tasks.

Purpose: how the hard engine works, what a task file contains, what goes
in and out, and how Blockly connects.

Status: 2026-11-21.
- Engine, Blockly side, two-dimensional score and the S1 task are done.
- The household half of the simulation runs the tasks. The market half
  ([market_sim.md](market_sim.md)) supplies the fund's returns.
- 110 tests in `backend/data`.
- One submission takes about 150 ms.

Architecture: [architecture.md](architecture.md). Spec it implements:
[task_engines.md](task_engines.md), "Hard engine".

## How a submission is scored

1. **Convert.** If the app sends a Blockly workspace (JSON with a `blocks`
   key), it is converted to our program JSON (`hard/blockly.py`).
2. **Check.** The program may use only the task's palette and values, and
   must stay within the block and depth limits. A failed check returns an
   error list; nothing runs.
3. **Compile** into a policy. It is interpreted; user code never runs.
4. **Obligatory tests:** named scenarios with a check.
   - If any fails, the result is "not accepted", with the failing test's
     month-by-month `story`.
5. **Optional tests:** named scenarios, each with a probability. Each gets a
   metric:
   - 1 = never needed the card;
   - 0.5 = needed it but repaid it by the end;
   - 0 = still in debt.
6. **Resilience points** = 51 + 49 × (probability-weighted share of the
   optional metrics). The attempt stores `points` (51-100) and `score` =
   points / 100.
7. **Futures:** 200 random futures, 10 years in S1 (`futures.months`), with
   random job losses and shocks and a fixed seed. Two results:
   - `without_card_debt`: in how many futures the rule never needed the
     card;
   - `growth_index`: the median net worth at the end, as an index where
     the reference solution = 100. This is the **second axis**, decided
     2026-11-21.

**Why two axes.** One number rewarded the biggest buffer. Two axes show the
trade-off, like LeetCode's separate runtime and memory percentiles.

| Program (S1) | Resilience | Growth | 10-year futures without the card |
|---|---|---|---|
| Reference: pay card debt, then a 3-month buffer, then invest | 97 | 100 | 133 / 200 |
| Bot: 6-month buffer, then invest | 100 | 98 | 182 / 200 |
| Bot: 2-month buffer, then invest | 91 | 97 | 90 / 200 |
| Bot: invest everything | not accepted | - | - |

The bots and the reference are scored at build time and shipped in the
question, so the scatter (resilience × growth) and the histograms have
reference points before there are users. A test keeps the trade-off true.
If content changes make the 6-month buffer win on both axes, the build's
tests fail.

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
5. **Interest and returns.** Buffer interest, card interest and the fund's
   return from the market path are applied.

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
| Numbers | `number`, `var`, `math` (`*`, `+`, `-`, `min` = "but at most") |

**Values:**
- `cash`;
- `shortfall`;
- `buffer_months`;
- `buffer`;
- `costs`;
- `card_debt`;
- `invested`;
- `employed`;
- `month`.

Each has an English label in `VARS`.

## Blockly (hard/blockly.py)

`question_view` contains everything the app needs under
`question.blockly`.

| Field | What the app does with it |
|---|---|
| `blocks` | `Blockly.common.defineBlocksWithJsonArray(blocks)`. Generated from the task's palette: block type `fq_<block>`; typed inputs (`Boolean`, `Number`) so wrong blocks do not snap; dropdowns for comparisons, operations and values (with the English labels); the root block `fq_every_month` with one statement input `DO`, not deletable |
| `toolbox` | A category toolbox (Rules, Conditions, Numbers, Actions). Numbers has one ready-made value block per allowed value |
| `starter` | `Blockly.serialization.workspaces.load(starter, workspace)` |

**Submit:** send `Blockly.serialization.workspaces.save(workspace)` as is.
The backend converts it. Loose blocks outside "Every month" are ignored;
an empty slot or two roots return an error to show.

**After submission:** `reveal.reference_workspace` loads the reference
solution into a read-only workspace.

**Flutter.** Blockly is JavaScript. On the web build, embed it with JS
interop or an `HtmlElementView`; on phones, use a webview. Fallback for
the demo: a Flutter rule builder that produces the same program JSON. The
engine accepts both formats.

## A task file (`hard:` in the node file)

See `backend/content/nodes/S1.yaml`.

| Field | Meaning |
|---|---|
| `id`, `level`, `content_version`, `author`, `reviewer`, `sources` | As for the other engines; `id` is `<node>.h<n>` |
| `brief`, `editorial` | Text before and after |
| `palette`, `vars`, `limits`, `starter_program` | What the user can build with |
| `household` | `income`, `costs`, `buffer`, optional `invested`, `card_debt`, `buffer_rate`, `card_rate` |
| `world` | `months`; `market`: any kind from market_sim.md, plus `asset` (which asset is the household's fund) |
| `assumptions` | Shown on screen; every illustrative number is listed |
| `obligatory` | `{name, override, check}`. `check` is `no_card_debt`, `contributed_at_least` or `net_worth_at_least` |
| `optional` | `{name, probability, override}` |
| `override` | `job_loss: [[month, length]]`, `shocks: {month: amount}`, `price_rise: [month, +x]` |
| `futures` | `n`, `months` (may be longer than the tests), `seed`, `job_loss_per_month`, `job_loss_months: [min, max]`, `shock_per_month`, `shock_amount: [min, max]` |
| `reference_program`, `known_bad_programs` (with `fails`), `baseline_bots` | The golden checks, and the points for the scatter and histograms |

**The build** (`python build.py --strict` for every engine) runs the golden
checks:
- the reference must be accepted;
- each known-bad program must fail the test it names.

A task that fails them is left out.

## API

```python
from hard import load_records, question_view, reveal_view, score
rec = load_records()["s1.h1"]
question_view(rec)          # GET /tasks/s1.h1: brief, palette, values, limits, blockly {blocks, toolbox, starter},
                            #   household, assumptions, obligatory test names, bots (points, growth_index)
score(rec, workspace_or_program)
                            # POST /answers: accepted, points, score, growth_index, obligatory, optional,
                            #   story (if rejected), futures
reveal_view(rec)            # reference program and workspace, editorial, optional events
```

The question never contains:
- the reference program;
- the optional events;
- the editorial;
- `meta`.

A test checks this.

## Not yet

- **A multi-asset household** and a `rebalance` action, for P4
  (market_sim.md, "Next for P4").
- **A JSON schema** for `output/hard_tasks.json`.
- **API wiring** (Mohamed):
  - `Catalog.find` loads `hard.load_records`;
  - the attempt stores `points` and `growth_index`;
  - percentiles per axis come from stored attempts.
