# Hard engine: block programs on the simulation core

Readers:
- Yurii (engines);
- Mohamed (API);
- Michał (the Blockly screen);
- content authors writing hard tasks.

Purpose: how the hard engine works, what a task file contains, what goes
in and out, and how Blockly connects.

Status: 2026-11-21.
- Engine, Blockly side and two-dimensional score are done.
- Two live tasks, both rebuilt as harder situations on 2026-11-21 (see
  "Next version" below):
  - p1.h1, "Ania's first two years": the young-adult capstone;
  - p4.h1 v2, "Marek over ten years": the investor capstone.
- s1.h1 and p4.h1 v1 are kept as frozen fixtures
  (`data/tests/fixtures/hard_baseline`). The S1 tables below describe that
  fixture.
- The household half of the simulation runs the tasks. The market half
  ([market_sim.md](market_sim.md)) supplies the fund's returns.
- 135 tests in `backend/data`.
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
     the reference solution = 100, with one decimal. This is the **second
     axis**, decided 2026-11-21.

**Why two axes.** One number rewarded the biggest buffer. Two axes show the
trade-off, like LeetCode's separate runtime and memory percentiles.

| Program (S1) | Resilience | Growth | 10-year futures without the card |
|---|---|---|---|
| Reference: pay card debt, then a 3-month buffer, then invest | 97 | 100 | 133 / 200 |
| Bot: 6-month buffer, then invest | 100 | 98 | 182 / 200 |
| Bot: 2-month buffer, then invest | 91 | 97 | 90 / 200 |
| Bot: invest everything | not accepted | - | - |

| P4 program | Resilience | Growth |
|---|---|---|
| Reference: rebalance when more than 5 points off 60/40 | 100 | 100.0 |
| Bot: rebalance every month | 100 | 100.2 |
| Bot: rebalance once a year | 93 | 100.0 |
| Bot: rebalance when 10 points off | not accepted: leaves the 50-70% band in the rally test | - |
| Bot: never rebalance | not accepted | - |
| Known bad: panic seller (sells everything after a 15% fall) | not accepted: the crash test | - |

**Finding (P4):** how often you rebalance barely changes growth. With a
0.1% cost, the bots differ by 0.2 index points. The lesson of P4 is
discipline: stay in the band and do not sell in a crash.
P4's optional
tests therefore score whether the mix stayed in the 50-70% band
(`optional_metric: band`), not card use.

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
   - `sell_investments` (pro rata over the holdings);
   - `pay_debt`;
   - `save_to_buffer`;
   - `invest` (in the `target` mix, or the single fund);
   - `rebalance` (back to `target`; `trade_fee` on both legs of the money
     moved).

   Each action is capped by what is available.
3. **Shortfalls.** Still short: the buffer pays, then the credit card.
4. **Leftovers.** Cash left over is spent: what you do not assign, you
   spend.
5. **Interest and returns.** Buffer interest, card interest and each
   asset's return from the market path are applied. Investments are
   holdings per asset: one fund in S1, shares and bonds in P4.

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
| Statements | `if_else`, `if`; actions `save_to_buffer`, `save_to_pot`, `invest`, `pay_debt`, `sell_investments` (each with an `amount`), `invest_in` and `sell` (an `amount` and an `asset`), `rebalance` (no input); own variables `set_var`, `change_var` (a `name` and a `value`) |
| Conditions | `compare` (`<`, `>`), `and`, `or`, `not` |
| Numbers | `number`, `var`, `my_var` (own variable), `math` (`*`, `+`, `-`, `/`, `min` = "but at most", `max` = "but at least") |

**Values:**
- `cash`;
- `shortfall`;
- `buffer_months`;
- `buffer`;
- `costs`;
- `card_debt`;
- `invested`;
- `employed`;
- `month`;
- for multi-asset tasks: `shares_weight`, `drift`, `drawdown`,
  `months_since_rebalance`;
- for the optional mechanisms: `income`, `pot`, `next_bill`,
  `months_to_next_bill`, `target_shares`, `years_to_goal`,
  `tax_due_this_year`.

Each has an English label in `VARS`.

## Blockly (hard/blockly.py)

`question_view` contains everything the app needs under
`question.blockly`.

| Field | What the app does with it |
|---|---|
| `blocks` | `Blockly.common.defineBlocksWithJsonArray(blocks)`. Generated from the task's palette: block type `fq_<block>`; typed inputs (`Boolean`, `Number`) so wrong blocks do not snap; dropdowns for comparisons, operations, values and assets (with the English labels); the root block `fq_every_month` with one statement input `DO`, not deletable |
| `toolbox` | A category toolbox (Rules, Conditions, Numbers, My variables, Money moves). Numbers has one ready-made value block per allowed value. Every number slot carries a typed number (a shadow `fq_number`). "My variables" is Blockly's dynamic category (`"custom": "VARIABLE"`): it needs Blockly's default blocks registered (`import 'blockly'`, not only `blockly/core`) |
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

See `backend/content/nodes/P1.yaml` (the capstone: bills, card minimum,
three assets) and `P4.yaml` (shares and bonds, moving target, fees, tax).
The frozen `data/tests/fixtures/hard_baseline/s1_h1.yaml` is the simplest
example (one fund).

| Field | Meaning |
|---|---|
| `id`, `level`, `content_version`, `author`, `reviewer`, `sources` | As for the other engines; `id` is `<node>.h<n>` |
| `brief`, `editorial` | Text before and after |
| `palette`, `vars`, `limits`, `starter_program` | What the user can build with |
| `assets` | `{asset: label}`: the assets `invest_in` and `sell` may name (keys of `household.invested`) |
| `household` | `income`, `costs`, `buffer`, `invested` (a number for one fund, or `{asset: value}`), `target` (`{asset: weight}`), `trade_fee`, `card_debt`, `buffer_rate`, `card_rate`. Optional: `bills`, `pot`, `card_min_payment`, `sell_fee`, `broker_fee`, `glide`, `tax_on_gains` (see "Next version") |
| `world` | `months`; `market`: any kind from market_sim.md. With `asset`, only that asset is the fund (s1.h1); without it, every asset on the path is held. Optional `income_extra: {min, max, seed}` |
| `assumptions` | Shown on screen; every illustrative number is listed |
| `obligatory` | `{name, override, check}`, optional `variants` (several overrides; all must pass). `check` is `no_card_debt`, `no_new_card_debt`, `contributed_at_least`, `net_worth_at_least`, `weight_between: {asset, low, high}`, `weight_at_least: {asset, value}` or `weight_near_target: {asset, below, above}` (weights at every month end) |
| `optional` | `{name, probability, override}` |
| `optional_metric` | Default: card use (1 = never borrowed on the card; 0.5 = borrowed but ended no higher than it started; 0 = more debt). `{band: {asset, low, high}}` or `{near_target: {asset, below, above}}` scores whether the mix stayed in the band |
| `override` | `job_loss: [[month, length]]`, `shocks: {month: amount}`, `price_rise: [month, +x]`, `returns: {asset: {month: r}}`, `trend: [{asset, from, to, r}]` |
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
rec = load_records()["p1.h1"]
question_view(rec)          # GET /tasks/p1.h1: brief, palette, values, assets, limits, blockly {blocks, toolbox, starter},
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

## Next version: harder situations (designed and built 2026-11-21)

**Built.** Measured results (resilience points / growth index):

| p1.h1 program | Result |
|---|---|
| Reference | 95 / 100 |
| Buffer of 3 months, no pot, card left at the minimum | 84 / 99.8 |
| Like the reference, but everything in CrocoTech | 95 / 96.2 |
| Like the reference, but everything in the bond | 95 / 94.1 |
| Lazy rules: "save 1,000, invest the rest", "buffer of 2 months, no bills pot", "invest everything", "buffer only" | not accepted |

"Save 1,000, invest the rest" survives a job loss starting in month 10, 15
or 20 and fails only the month-5 timing. The unknown timing is what
catches it.

| p4.h1 v2 program | Result |
|---|---|
| Reference | 100 / 100 |
| Rebalances every month | 100 / 97.4 |
| New money always into shares, rebalance at 5 points | 100 / 98.7 |
| Rebalances once a year | 76 / 99.1 |
| Never rebalances; panic seller | not accepted |

**Changed while building** (the design text below is kept, these replace
it):
- The minimum fee is `broker_fee: {rate, min}` instead of
  `trade_fee_min`. It applies to every buy and sell leg; the old
  `trade_fee` still applies only to rebalancing.
- The capstone has no `weight` value: the reference rule does not need it.
- The capstone's optional surprises are the ones that separate strategies:
  - car repair;
  - prices up 10%;
  - dentist;
  - 3-month job losses just before the holiday bill and over the car
    insurance;
  - a 4-month job loss;
  - an early job loss.

  Market events (CrocoTech, crashes) show on the growth axis instead.
- The bot "keep 60/40 forever" was dropped, because a fixed 60/40 cannot be
  written without the moving target.
- "The build checks the every-month bot loses growth" is a test in
  `data/tests/test_hard.py`, alongside the capstone's lessons.
- Fictional market calibration: calm months average 1.2%, so shares come
  out about 7% a year. The indexed bond is 0.35% a month. CrocoTech's
  average equals the fund's once its crash events are counted.
- The card's minimum payment is taken before the policy runs. If the month
  cannot cover it, the shortfall goes to the buffer, then the card, and
  that counts as borrowing.
- The demo paths say how the app shows each hard task
  (`router/demo_paths.yaml`, `hard:`):
  - young adult: p1.h1 is the capstone;
  - investor: p1.h1 is optional, p4.h1 is the capstone.

  Hard tasks never block finishing a node.

**Why.** Measured 2026-11-21: in S1, "save 1,000, invest the rest" (2
blocks, no condition) is accepted with 91 points; in P4, "rebalance every
month" scores 100. The situations are too simple to need a thought-out rule.

**Decided 2026-11-21** (Mateusz builds it; Yurii agreed):
- the tests keep their kinds: two obligatory checks, optional scenarios,
  200 futures. The situation gets more variables and real uncertainty, and
  combines concepts from the node and the nodes before it;
- the hard task moves from S1 to a capstone on P1, the last node of the
  young-adult path. S1 comes first on that path, so a user there has
  learned only F1;
- P4 gets 19% tax on realised gains, switched on for that task only.

### Where the new parts live

Three layers:
1. **Core:** the month loop (`sim/household.py`) and the block language
   (`hard/dsl.py`, `hard/blockly.py`). Each new mechanism is an optional
   field that is off by default.
2. **Task file:** the story and numbers, and which mechanisms are on.
3. **Regression baseline:** before any change, s1.h1 and p4.h1 as they are
   today are copied to `data/tests/fixtures`. After every step they must
   give the same points, growth index and bot results.

A layer outside the engine would not work: fees, bills and tax happen
inside the month, between the policy and the returns, where a wrapper
cannot reach.

| Mechanism | Task field or block | Used by | Changes |
|---|---|---|---|
| Own variables | blocks `set_var`, `change_var`, `my_var` | both | dsl, blockly |
| `if` without "otherwise" | block `if` | both | dsl, blockly |
| Divide, "but at least" | `math` ops `/`, `max` | both | dsl |
| Typed number in every slot | Blockly shadow block | both | blockly |
| Buy or sell one asset | blocks `invest_in`, `sell` with an asset dropdown | both | household, dsl |
| Irregular income | `household.income_extra: [min, max]`, drawn each month | p1.h1 | household |
| Yearly bills and a bills pot | `household.bills: [{name, amount, month, every}]`, block `save_to_pot` | p1.h1 | household |
| Card minimum payment | `household.card_min_payment` (share of the debt, paid first) | p1.h1 | household |
| Fee on selling one asset | `household.sell_fee: {asset: x}` | p1.h1 (the bond) | household |
| Minimum fee per trade | `household.trade_fee_min` | p4.h1 | household |
| Moving target mix | `household.glide: {asset, from, to}` (straight line over the months) | p4.h1 | household |
| Tax on realised gains | `household.tax_on_gains` | p4.h1 | household |
| Unknown timing in a test | `obligatory[].variants`: several overrides; all must pass | both | task |
| Card checks with starting debt | check `no_new_card_debt`: the card balance never goes up | p1.h1 | task |
| Weight checks with a moving target | check `weight_near_target: {asset, below, above}` | p4.h1 | task |

The value `month` is left out of both tasks. A rule must react to what
happens, not to a test month it can read in the brief.

### Own variables (Scratch's "Make a variable")

Scratch is built on Blockly, so the app uses Blockly's own variable
category: a "Make a variable" button, then "set [x] to ( )", "change [x]
by ( )", and [x] as a value.
- Numbers only. A variable starts at 0 and keeps its value from month to
  month. That is what makes it useful: "months since my last bonus",
  "money put aside for tax".
- At most 3 per program. Names use letters, digits and `_`, up to 20
  characters, and cannot reuse a built-in value name.
- The converter maps `variables_set`, `math_change` and `variables_get` to
  `{"block": "set_var", "name": "x", "value": <number>}`, `change_var` and
  `my_var`. Still interpreted, never run as code.
- Dividing by 0 gives 0; the help text says so.

**Typing inside blocks.** Every number slot holds a typed number, like
Scratch's white oval. You overwrite it by typing, or by dropping a value, a
calculation or your own variable on it.

### Tax on realised gains (P4 only)

Two kinds of number, kept only when `tax_on_gains` is set:
- **one cost basis per asset:** what was paid for the units still held;
- **one accumulator:** the gain realised this year.

The rules:
- Buying adds the money to the asset's cost basis.
- Selling X of an asset worth V with cost basis B:
  - the gain is X − B·X/V;
  - the cost basis falls by B·X/V;
  - the gain goes into the accumulator.

  Rebalancing counts as selling; the fee lowers the gain.
- Every 12th month the tax is `tax_on_gains` × max(accumulator, 0). It is
  paid from cash, then the buffer, then the card, and the accumulator goes
  back to 0.
- The program can read `tax_due_this_year`.

**Why no array.** An array of purchases (one entry per buy) is only needed
to sell the oldest units first (FIFO). One number per asset is enough for
the average price.

**Simplifications** (listed in `assumptions`):
- average price, not FIFO. Polish rules match a sale to the oldest
  purchase; check this before quoting it;
- tax at year end, not in April;
- losses do not carry over to the next year;
- no IKE/IKZE.

### p1.h1 capstone: "Ania's first two years" (F1, S1, I1, I2, I4, P1)

**Situation:** Ania, 27, over 24 months:
- base pay 5,800 PLN, plus 0-1,500 PLN of freelance work, unknown until
  the month starts;
- essentials 4,800 PLN;
- a buffer of 4,000 PLN at 4%;
- card debt of 3,000 PLN at 20%, minimum payment 3% a month;
- yearly bills: car insurance 1,800 PLN in month 9 and a holiday 2,500 PLN
  in month 14, each every 12 months.

| Where money can go | Concept | Engine |
|---|---|---|
| Buffer (ready at once, 4%) | S1 | as today |
| Bills pot (for the known bills) | F1 | new |
| Inflation-indexed savings bond: inflation plus a margin; 1% fee if sold early | I2: money that is locked, so a poor home for the buffer | `sell_fee` |
| Broad share fund | I4 | `fictional` market, beta 1 |
| One company, fictional "CrocoTech" | I4, I1: same average return, wider spread, rare crashes, so a lower typical result | `fictional` market, beta 1.3, events |
| The mix of all of these | P1 | `invest_in` |

**Obligatory** (same kinds as s1.h1):
1. A 2-month job loss starting in month 4, 8, 13 or 19 (all four must
   pass): the card balance never goes up.
2. A normal 24 months: at least 12,000 PLN invested.

**Optional** (with probabilities, scored on card use as in s1.h1):
- CrocoTech loses 60%;
- an inflation jump (the bond does best);
- a share crash in year 2;
- a car repair of 3,000 PLN;
- a 4-month job loss;
- a month with a large bonus.

**Values the program can read:** `cash`, `income`, `costs`,
`buffer_months`, `pot`, `next_bill`, `months_to_next_bill`, `card_debt`,
`invested`, `weight` of an asset, `employed`, plus own variables.

**Reference rule** (draft, about 20 blocks):
1. If the buffer covers less than 1 month, fill it.
2. Otherwise, if there is card debt, pay it off.
3. Put next_bill ÷ months_to_next_bill into the bills pot.
4. Fill the buffer to 3 months.
5. Invest the rest: most in the fund, some in the bond, little or nothing
   in CrocoTech.

**Must fail or lose:**
- "save 1,000, invest the rest": the bills drain the buffer, and the
  job-loss test fails;
- "buffer only": the investing test fails;
- "everything in CrocoTech" is accepted but has a lower growth index. It
  is a bot on the scatter.

**Limits:** 40 blocks, depth 5.

**Switching over.** s1.h1 stays live until p1.h1 passes its golden checks.
Then:
- S1 keeps its cards and easy items;
- s1.h1 becomes the regression fixture;
- the API tests move to p1.h1.

**Open:** P1 is also on the investor path (I4 → I5 → P1 → P4), so
investors meet the capstone too. Either keep it, or make p1.h1 optional on
that path.

### p4.h1 v2: "Marek over ten years" (P4, P2, P1, I5, I4)

**Situation:**
- 120 months for the tests and the futures;
- 100,000 PLN in 60/40, plus 1,000 PLN a month;
- the goal is 10 years away, so the share target falls from 60% to 40% in
  a straight line (P2);
- costs: a trade fee of 0.29%, at least 5 PLN per trade (I5), and 19% tax
  on realised gains;
- new money can go to either asset (`invest_in`);
- market: `fictional` until the real series is in (`bootstrap` after),
  with a regime where shares and bonds fall together (P1, 2022).

**Obligatory** (same kinds; the bounds follow the moving target):
1. A long rally: shares stay within 10 points of the month's target.
2. A crash starting in month 6, 40 or 100 (all must pass): shares never
   fall more than 20 points below the target. This rules out panic
   selling.

**Optional:**
- shares and bonds fall together;
- a crash in year 9, close to the goal;
- a long sideways market, where fees add up;
- a fast rally.

**Values:** `cash`, `shares_weight`, `target_shares`, `drift`, `drawdown`,
`months_since_rebalance`, `years_to_goal`, `tax_due_this_year`, plus own
variables.

**Reference rule** (draft):
1. Put new money into the asset below its target.
2. Rebalance only if the drift is more than 5 points and the money to move
   is above 1,000 PLN.

**Must fail or lose:**
- "never rebalance" and "keep 60/40 forever" fail the rally test;
- "rebalance every month" is accepted but pays fees and tax every month.
  The build checks that its growth index is below the reference's, so the
  lesson stays true when numbers change.

### Blocks to choose from

| Toolbox category | Blocks | p1.h1 | p4.h1 |
|---|---|---|---|
| Rules | `if`, `if_else` | 2 | 2 |
| Conditions | `compare` (is less than, is more than), `and`, `or`, `not` | 4 | 4 |
| Numbers | typed number, value (dropdown), calculation (plus, minus, times, divided by, but at most, but at least) | 3 | 3 |
| My variables | set, change, the variable | 3 | 3 |
| Money moves | p1.h1: `save_to_buffer`, `save_to_pot`, `pay_debt`, `invest_in` [asset], `sell` [asset]. p4.h1: `invest_in` [asset], `sell` [asset], `rebalance` | 5 | 3 |
| **Total block types** | | **17** | **15** |

Today each task has 10. The dropdowns carry the choice: 11-12 values and 2-4
assets per task. Five categories keep the toolbox short.

### Build order and cut line

| Step | What | Check |
|---|---|---|
| 1 | Freeze the regression baseline (s1.h1 and p4.h1 v1 as fixtures) | existing results unchanged |
| 2 | Language: own variables, `if`, divide, "but at least", typed slots, `invest_in` and `sell` per asset | dsl and blockly tests; baseline unchanged |
| 3 | p4.h1 v2: moving target, minimum fee, tax | golden checks; the every-month bot loses on growth |
| 4 | p1.h1: irregular income, bills pot, card minimum, sale fee, test variants; then switch S1 → P1 | golden checks; the lazy rules fail as listed |

Each step ends with all suites passing. If time runs out, the tasks from
the last finished step stay live. Michał should hear about step 2 before he
builds the hard-task screen: the variable category and the asset dropdowns
change what Blockly shows.

## Not yet

- **P4 on real data:** switch `world.market` to `replay` (2020) or
  `bootstrap` once the monthly series are in the store (market_sim.md).
- **Tax on realised gains:** designed above for P4 only. Today P4 assumes
  an IKE-like account.
- **A JSON schema** for `output/hard_tasks.json`.
- **API wiring** (Mohamed):
  - `Catalog.find` loads `hard.load_records`;
  - the attempt stores `points` and `growth_index`;
  - percentiles per axis come from stored attempts.
