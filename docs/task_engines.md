# Task engines: easy, medium, hard

Readers:
- backend (Mohamed): scoring endpoints;
- frontend (Michał): renderers;
- Yurii: the hard engine and the data series;
- content authors: task files.

Purpose: one contract per task level, so that a new task is a content file,
not new code.

Status: draft for review on branch `skills-tree`, 2026-11-20. Task ideas per
node are in [skills_tree.md](skills_tree.md).

## Assumptions

1. **Authoring.** Content is written as one YAML file per node in
   `backend/content/nodes/<node_id>.yaml`. The validator
   (`validate_content.py`, named in the frontend README but not in the repo
   yet) checks the files and builds the JSON the app loads. If the team
   prefers JSON for authoring, the schema stays the same.
2. **Scoring runs in the backend.** The browser never receives correct
   answers, truth values or box weights before the user submits (as the
   backend README already states).
3. **Data.** Series come from one table
   `(series_id, date, value, source, licence)` (Yurii). Tasks refer to a
   `series_id`; they never embed raw prices.
4. **The hard engine's internals are Yurii's.** This file fixes only its
   inputs, outputs and tests.

## Shared parts

**Metadata on every task.**

```yaml
id: f4.m1                 # <node>.<level letter><n>
node: F4
level: easy | medium | hard
content_version: 3        # bump on any change that affects scoring
author: ...
reviewer: ...             # required before the task goes live
sources: [uokik_portal, rf_credit_costs]   # IDs from the source register
valid_until: 2026-12-31   # required when the task uses a limit, rate or tax rule
```

**Language.** The demo UI is English. Every user-facing text field may be a
plain string (English) or a map `{en: "...", pl: "..."}` for a later Polish
version. Polish names of instruments and institutions stay as they are, each
with an English explanation on first use (IKE, IKZE, PPK, KNF, BFG, RRSO =
APR). Amounts are in PLN.

**Confidence on every scored item.**
- The user answers "How sure are you?" from 1 to 5, mapped to
  p = (c − 1) / 4.
- It is stored, not scored.
- Calibration per user and per task is the Brier term (p − score)².

**Attempt record.** One row per submission. It feeds the learner model and
the author dashboard.

```
attempt_id, user_id, task_id, content_version, level,
response (JSON), confidence, score_estimate, score_reasons, score,
accepted (hard), started_at, submitted_at, hints_used, tutor_opened,
clarity_rating (1-5, optional)
```

**Author dashboard per task** (from attempts):
- n;
- mean score;
- mean confidence;
- calibration gap: mean p − mean score;
- confidence change before vs after the node;
- drop-off: started but not submitted;
- median time;
- clarity.

The main alert is "confidence rises, score does not": that task teaches
overconfidence.

**What the tutor receives:**
- the task text;
- the user's response;
- the reveal JSON after submission.

The tutor never sees truth values before submission or other users' data.

---

## Easy engine

Implementation guide (all five kinds, cards, prerequisite test): [easy_engine.md](easy_engine.md).

**Item kinds.**

| Kind | Response | Score |
|---|---|---|
| `single` | one option | 1 if correct, else 0 |
| `multi` | several options | (correct picks − wrong picks) / number of correct options, clipped to 0-1 |
| `true_false` | true / false | 1 / 0 |
| `numeric` | a number | tolerance rule from the medium engine |
| `reflection` | one option, no correct answer | not scored; feedback per option (today's "behaviour" questions) |

**Card.**

```yaml
cards:
  - id: f4.c1
    title: "RRSO: the full price of a loan"
    body: "..."            # at most 80 words, plain English
    example: "..."         # one example in PLN
    links: [uokik_portal]  # 1-2 source IDs, shown as links
    figure: null           # optional image or chart spec
```

**Item.**

```yaml
items:
  - id: f4.e1
    kind: single
    q: "..."
    options: ["...", "...", "..."]
    answer: 2              # never sent to the client
    why: "..."             # shown after the answer
    check: true            # may be drawn into prerequisite tests of later nodes
    difficulty: 0.0        # starting Elo difficulty; updated from attempts
```

**Prerequisite test.**
- 2-3 items drawn from items with `check: true` in the node's prerequisite
  nodes.
- Passing all of them marks the node's easy part as done.

**Compatibility.** Today's `roadmap.json` questions (`id, q, options,
answer, why, feedback, sources`) map one to one:
- with `answer`: `single`;
- with `feedback`: `reflection`.

---

## Medium engine: "estimate and explain"

Implementation guide (chart + direction so far): [medium_engine.md](medium_engine.md).

One renderer and one scorer. A task combines four parts:

| Part | What it is | Kinds |
|---|---|---|
| Stimulus | what the user sees | chart, table, offer, text, messages |
| Response | what the user gives | number, direction, choice, labels |
| Truth | where the correct value comes from | `calculator`, `fixed`, `none` |
| Reasons | boxes with author weights | always present |

**Task file.**

```yaml
id: f4.m1
node: F4
level: medium
variant: estimate          # estimate | day_x | label
brief: "Ewa borrows 20,000 PLN for 36 months. How much will she pay back in total?"
stimulus:
  - kind: offer
    fields: {kwota: 20000, okres_mies: 36, oprocentowanie: 0.099, prowizja: 0.08, ubezpieczenie: 0.03}
response:
  kind: number
  unit: PLN
  input: slider            # slider | field | drag_on_chart
  min: 20000
  max: 40000
  step: 100
truth:
  calculator: loan_cost
  args: {principal: 20000, months: 36, nominal_rate: 0.099, fee_rate: 0.08, insurance_rate: 0.03}
  output: total_payable
tolerance: {kind: relative, band: 0.10}
reasons:
  pick: {min: 2, max: 3}
  boxes:
    - {id: fee, text: "The fee is borrowed too, and interest is charged on it", weight: 1.0, explain: "..."}
    - {id: insurance, text: "Loan insurance adds to the total cost", weight: 0.8, explain: "..."}
    - {id: term, text: "A longer term means more interest", weight: 0.5, explain: "..."}
    - {id: nominal_only, text: "Only the nominal rate matters", weight: -1.0, explain: "..."}
    - {id: irrelevant, text: "The bank has a nice app", weight: 0.0, explain: "..."}
weights: {estimate: 0.5, reasons: 0.5}
reveal:
  text: "..."
  show: [truth, per_box_explain, sources]
```

**Stimulus kinds.**

| Kind | Fields | Notes |
|---|---|---|
| `chart` | `series: [{series_id, from, to, transform}]`, `type: line/bar/histogram/fan`, `cutoff`, `hide: [name, dates]` | `cutoff` hides data after day X until the reveal; `hide` anonymises the series. Transforms: `level`, `yoy`, `index100`, `rolling_n` |
| `table` | `rows` | Small, at most about 8 rows |
| `offer` | `fields` | Rendered as an offer sheet |
| `text` | `body` | Persona story, report excerpt, news headline |
| `messages` | `items: [{sender, time, body, link}]` | For scam tasks |

**Response kinds.**

| Kind | Fields | Estimate score |
|---|---|---|
| `number` | `unit, input, min, max, step`; `x` for `drag_on_chart` | tolerance rule below |
| `direction` | `options: [up, down, flat]` | 1 / 0 when truth exists; none for `day_x` |
| `choice` | `options` | 1 / 0 |
| `labels` | `items`, `classes` (e.g. the 2×2 decision/outcome) | share of items labelled correctly |

**Truth kinds.**
- `calculator`: a named function from the registry below, with arguments
  in the task file.
- `fixed`: an author-set value or label, for example the fee printed in a
  KID.
- `none`: for `day_x`. The outcome is shown at the reveal but not scored.

**Scoring.**

1. Estimate, for `number`. Let t be the truth and x the answer.
   - The tolerance band is d = band × |t| for `relative`, or d = band for
     `absolute`.
   - r = |x − t| / d.
   - The estimate score is 1 when r ≤ 1, then 1 − (r − 1) / 2 up to r = 3,
     then 0.
2. Reasons. Let P be the set of boxes the user picked and k = |P|.
   - The best possible sum is the k largest of max(w, 0) over all boxes.
   - The reasons score is the sum of the picked weights divided by that
     best sum, clipped to 0-1.
3. Task score:
   - `day_x`: the reasons score only.
   - Otherwise: weights.estimate × estimate score + weights.reasons ×
     reasons score.

Worked check: t = 30,000, band 10%, so d = 3,000.
- x = 32,000 gives r = 0.67 and an estimate score of 1.
- x = 36,000 gives r = 2 and an estimate score of 0.5.
- x = 40,000 gives r = 3.33 and an estimate score of 0.

**Calculator registry.** Pure functions, each with a unit test against a
hand-worked example. This list covers the medium idea of every node:

| Calculator | Output | Nodes |
|---|---|---|
| `ledger_balance` | balance on a date from a persona ledger | F1 |
| `min_buffer` | smallest buffer (months of costs) that keeps the ledger above zero | S1 |
| `real_value` | value of an amount after CPI over a period | F2 |
| `annuity_fv` | future value of regular contributions | F3, S2 |
| `required_saving` | monthly saving to reach a goal | S4 |
| `loan_cost` | schedule, total payable, RRSO (IRR of the cash flows) | F4, S2 |
| `annuity_payment` | instalment for a rate scenario | L2 |
| `event_probability` | 1 − (1 − p)^n and expected count | S3 |
| `expected_loss` | yearly expected loss vs premium | S3 |
| `proportion_rule` | payout under underinsurance | S3 |
| `series_stats` | count of negative years, worst year, from a series | I1 |
| `mix_stats` | worst year and spread of a fixed mix | P1 |
| `rolling_window_share` | share of n-year windows ending below the start | P2 |
| `lump_vs_instalments` | end values of both on one path | P3 |
| `bond_price_change` | approximate price change from duration and rate change | I3 |
| `fee_drag` | difference in end value for two cost levels | I5 |
| `fx_return` | result in PLN from a foreign return and an FX move | I6 |
| `leverage_loss` | share of deposit lost for leverage and price move | I7 |
| `pe_ratio` | P/E from price, profit and share count | D2 |
| `overtrading_cost` | diary result vs buy-and-hold on the same path | D4 |
| `ppk_balance` | PPK value with employer and state contributions | L1 |
| `depletion_year` | year money runs out for a withdrawal plan and path | L3 |
| `capital_gains_tax` | 19% tax with costs and loss offset | O3 |
| `guarantee_coverage` | BFG and KDPW coverage in PLN at the NBP EUR rate | O4 |

Tasks without a calculator:
- `day_x` (I2, I4, P4, P5, D1, D3): truth `none`;
- O1 and O2: truth `fixed`;
- D5: `labels` with author labels.

**API.**
- `GET /tasks/{id}` returns the task without `truth`, `answer`, weights or
  explanations.
- `POST /answers` with `{task_id, response, confidence, reasons}` returns
  the scores and the reveal.

**Validator checks.**
- Every `series_id` exists and its licence allows display.
- Every `calculator` exists and its arguments match its signature.
- At least one box has a positive weight.
- `day_x` tasks have a `cutoff`.
- `valid_until` is not in the past.

---

## Hard engine: blocks compile to a strategy

Yurii owns the internals. This section fixes what goes in and what comes out.
The engine runs on the shared simulation core `sim/`, which the sandbox and
historical replays will also use ([architecture.md](architecture.md)).

**Task file.**

```yaml
id: s1.h1
node: S1
level: hard
brief: "..."
palette: [if_else, compare, months_of_costs, save_to_buffer, pay_debt, invest, wait]
starter_program: starters/s1_h1.json     # empty, partial, or 3 full plans for the easiest ramp
limits: {max_blocks: 25, max_depth: 4}
state: {age: 26, income_net: 6500, costs: 4800, buffer: 2000, card_debt: 0}
world:
  modules: [income, job_loss, expense_shocks, inflation_pl]
  months: 24
  futures: 1000
  seed: 2026112001                       # fixed per content_version
obligatory:                              # each must pass; together worth 51
  - {name: "Job loss in month 4, lasting 3 months", override: {job_loss: {month: 4, length: 3}}, check: "min_balance >= 0"}
optional:                                # events weighted by probability, worth up to 49
  - {name: "Car repair, 3,000 PLN", probability: 0.25, override: {expense_shock: {amount: 3000}}, metric: "min_balance >= 0"}
  - {name: "Two shocks in one year", probability: 0.08, override: {...}, metric: "min_balance >= 0"}
reference_program: refs/s1_h1.json
known_bad_programs: [bad/s1_h1_all_in.json]
baseline_bots: [{name: "Saves nothing", program: bots/none.json}, {name: "Everything in a deposit", program: bots/all_deposit.json}]
editorial: editorials/s1_h1.md
```

**Program.**
- Blockly exports a JSON AST.
- Blocks are typed:
  - conditions return a boolean;
  - actions change the ledger;
  - control blocks are if / else and "every month".
- Each block shows an English sentence template with amounts in PLN.
- The engine interprets the AST. User code is never executed.

**Engine API.**
- `validate(program, task)`: returns a list of errors, such as a block not
  in the palette, the limits exceeded, or an empty action slot.
- `run(program, task)`: visible examples only, free and unlimited. Returns
  monthly ledgers for the examples.
- `submit(program, task)`: obligatory and optional tests. Returns the result
  below.

**Scoring.**
- Any obligatory test fails → not accepted. The response names the first
  failing test and shows its story: "test 2: job loss in month 4…". There
  is no score, and resubmission is allowed.
- All obligatory tests pass → accepted, and the score is 51 plus 49 times
  the probability-weighted share of optional tests passed.
  - Each optional test e has a probability p_e and a result m_e from 0 to
    1. This is pass/fail, or the result relative to the reference program
    capped at 1.
  - The weighted share is Σ p_e·m_e / Σ p_e.
- The histogram shows accepted scores per `content_version`, with the
  baseline bots marked.
- Common seeds give every user the same futures, so scores are comparable.

**Result JSON.**

```json
{
  "accepted": true,
  "score": 87,
  "obligatory": [{"name": "...", "passed": true}],
  "optional": [{"name": "...", "probability": 0.25, "metric": 1.0}],
  "percentile": 72,
  "story": {"test": "...", "months": [{"m": 1, "income": 6500, "costs": 4800, "buffer": 3700}]}
}
```

**Engine tests, per task, in CI.**
- The reference program is accepted with a score of at least 90.
- Every known-bad program is rejected.
- The same program and `content_version` give the same score twice
  (determinism).
- `submit` finishes within 2 s for 1,000 futures.

---

## Data series and licences

Only series whose terms allow display in our app. Each row in the series
table carries `source` and `licence`.

| Source | Series | Use | Licence status (2026-11-20) |
|---|---|---|---|
| GUS, Knowledge Databases (DBW) | CPI, household budgets | F1, F2, I2, D3 | CC BY 4.0 for DBW data, according to the DBW terms page (from search). Site-wide terms at stat.gov.pl/copyright: to read |
| Eurostat | HICP for Poland and the EU | F2 backup, EU comparison | European Commission reuse policy, attribution (to confirm) |
| NBP | Reference rate history, FX (API, from 2002), gold | F2, I2, I6, L2, D3 | The API page points to the "Regulaminy NBP": to read before showing it |
| Ministry of Finance | Retail bond series: rates, redemption fees | I2 | Public offer terms; reuse terms to read |
| ECB Data Portal | Euro-area rates, HICP | D3, P5 | ECB reuse with source citation (to confirm) |
| OECD Main Economic Indicators | Share price index for Poland (monthly, 2015 = 100); long-term government bond yield | I1, P1, P4 | OECD open access since 1 July 2024; CC BY 4.0 stated for content, data terms to confirm. Also on FRED as SPASTT01PLM661N. **Price index, not total return** |
| Damodaran (NYU) | Annual US stocks, bonds, bills since 1928 | I1, P1, P2, P5 | Free download, no stated licence: attribution; ask before commercial use |
| Shiller (Yale) | Monthly S&P composite, dividends, CPI | P3, P4 | Same as Damodaran |

**Not used:**
- GPW quotes and WIG20TR;
- MSCI indices;
- stooq;
- Yahoo Finance;
- justETF;
- Morningstar.

These are licensed or have restrictive terms. backend/data/README.md still
lists GPW and MSCI: to discuss with Yurii.

**Licence checklist, for a person to verify before a series goes into a
task.** For each source, answer:
1. Is commercial use allowed?
2. What attribution does it require, and in what form?
3. May we store a copy (a CSV in the repo or in the database)?
4. May we show charts derived from it?
5. Is there a non-commercial (NC), no-derivatives (ND) or share-alike (SA)
   clause?
6. Do the terms of the download channel (API, FRED) add anything?

| Source | Where the terms are | Needed for |
|---|---|---|
| GUS | [DBW terms](https://dbw.stat.gov.pl/en/warunki-wykorzystania); [stat.gov.pl/copyright](https://stat.gov.pl/copyright) | CPI (I2, F2), household budgets (S1) |
| NBP | "Regulaminy NBP", linked from [the FX download guide](https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/instrukcja-pobierania-kursow-walut) | reference rate (I2), FX (I6) |
| Ministry of Finance | [obligacjeskarbowe.pl](https://www.obligacjeskarbowe.pl/), footer terms; the archive of series rates | retail bond rates (I2) |
| OECD | Terms and conditions, linked from [the open-access announcement](https://www.oecd.org/en/about/news/press-releases/2024/07/oecd-data-publications-and-analysis-become-freely-accessible.html) | share price index Poland (I1, I5, P1, P4); long-term yield (P1) |
| Eurostat | Copyright notice on the Eurostat site | HICP (backup for CPI) |
| Damodaran | [data page](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html): no licence stated | stocks, bonds, bills (I1, P1) |
| Shiller | [data page](http://www.econ.yale.edu/~shiller/data.htm): no licence stated | monthly S&P (P4 backup) |

**Repo rule (organisers).** Third-party data under a permissive licence (CC
BY 4.0 or similar) needs attribution, not a licence file in our repo. Keep
one attribution list:
- in `backend/data/SOURCES.md`, with source, URL, licence, date retrieved
  and changes made;
- in the app's "Sources" screen.

Ask the organisers whether data files may be committed, or must be
downloaded by a script at build time.

**Single companies** (I4, D1, D2) are not on the young-adult path. Until a
licensed source is found, I4 uses a synthetic company path, labelled as such
on screen. Company reports are public, but price series are not.

## Node completion

A node is **done** when either:
- the user passed its **challenge** (test-out): 2 of the node's check items,
  both right, one attempt (decided 2026-11-21); or
- the prerequisite test was passed or the easy items average at least 0.8,
  **and** one medium task scores at least 0.6.

Hard tasks are optional for completion. They add score, the histogram and
the "mastered" badge.

## Can one engine serve all medium tasks?

Yes. Every medium idea in skills_tree.md maps to one stimulus, one response
kind and one truth kind. The per-task work is a content file plus, at most,
one new calculator.

Risks:
- **Chart input on mobile** (`drag_on_chart`): fall back to a slider.
- **RRSO** needs an IRR solver; test it against a worked example from UOKiK
  or the Financial Ombudsman.
- **Licence per series** for any chart a user sees.
