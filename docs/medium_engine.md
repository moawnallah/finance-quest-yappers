# Medium engine: implementation guide

Readers:
- backend (Mohamed): loading tasks, the API and scoring;
- frontend (Michał): the JSON to render;
- content authors: writing tasks and adding data;
- developers: adding new kinds.

The spec is [task_engines.md](task_engines.md), "Medium engine". This file
describes the code in `backend/data/medium/`. Status: 2026-11-20, owner Yurii.

## What is implemented

| Part | Implemented | Later (spec) |
|---|---|---|
| Stimulus | `chart` (line) | `table`, `offer`, `text`, `messages` |
| Response | `direction` (up / down / flat) | `number`, `choice`, `labels` |
| Truth | `none` (day X), `outcome` (the realised direction) | `calculator`, `fixed` |
| Reasons | weighted boxes, the spec's scoring | - |
| Variant | `day_x` | `estimate`, `label` (validated, but need the kinds above) |

Day X: the chart stops on a past date (the `cutoff`). The user sees only
what was known then, predicts a direction, rates confidence and picks reason
boxes. The reveal shows what happened next. Day-X tasks are graded on
reasons only, because the outcome cannot be known from the information on
day X.

## Files

```
backend/content/nodes/<NODE>.yaml       task content, one file per skills-tree node (copy _TEMPLATE.yaml)
backend/data/series/series.csv          the series table: series_id, date, value, source, licence
backend/data/series/catalog.yaml        one entry per series: name, unit, frequency, licence, display, synthetic
backend/data/SOURCES.md                 attribution list
backend/data/medium/
  series.py     the table, transforms (level, index100, yoy), synthetic paths
  parts.py      one registry per part: STIMULI, RESPONSES, TRUTHS, plus reasons
  task.py       validate -> compile -> question_view / reveal_view -> score
  build.py      command line and QA report
backend/data/schemas/medium_tasks.schema.json   contract for the output
backend/data/output/medium_tasks.json           built tasks (committed)
backend/data/output/medium_qa.md                QA report of the last build
```

## Build

```bash
cd backend/data
pip install -r requirements.txt     # pyyaml; jsonschema and pytest for tests
python -m medium.build --strict     # exit 1 if any task has an error
python -m pytest tests
```

Read `output/medium_qa.md` after every build:
- ✅ ok;
- ⚠️ built with warnings (e.g. no reviewer yet, cutoff on a weekend);
- ❌ left out of the output. A message like "expected down but the data says
  up" means the event must be fact-checked.

## Backend

Everything the backend needs is four functions.

```python
from medium import load_records, question_view, reveal_view, score, AttemptError

tasks = load_records()          # {task_id: record}, from output/medium_tasks.json

# GET /tasks/{id}
question_view(tasks[tid], lang="en")

# POST /answers  {task_id, response, reasons, confidence}
try:
    result = score(tasks[tid], response="down", reasons=["guidance", "capex"], confidence=4)
except AttemptError as e:       # wrong option, unknown or duplicate box, pick count, confidence
    ...                         # -> 400 with the message
return {**result, "reveal": reveal_view(tasks[tid], lang="en")}
```

Rules:
- Send only `question_view` before the answer. The record also holds `reveal`
  (outcome, weights, explanations, real names, dates) and `meta` (internal).
- `record["live"]` is false until a reviewer has signed the task off. Don't
  serve tasks that aren't live in production.
- `score()` returns the attempt-record fields from the spec; store them as
  they are:

```json
{
  "task_id": "d1.m1", "content_version": 1, "level": "medium",
  "response": {"value": "down", "reasons": ["guidance", "capex"]},
  "confidence": 4, "p": 0.75,
  "score_estimate": null, "score_reasons": 1.0, "score": 1.0
}
```

- `score_estimate` is null for day X. `p = (confidence − 1) / 4` feeds
  calibration and is not scored.

## Frontend

`question_view` (trimmed):

```json
{
  "id": "d1.m1", "node": "D1", "level": "medium", "variant": "day_x", "content_version": 1,
  "brief": "Company X, a large software firm, reports quarterly results ...",
  "stimulus": [{
    "kind": "chart", "type": "line", "x_unit": "trading_day",
    "series": [{"label": "Company X", "unit": "index (cutoff = 100)",
                "points": [{"t": -1, "v": 100.95}, {"t": 0, "v": 100.0}]}],
    "synthetic": true,
    "attribution": []
  }],
  "response": {"kind": "direction", "options": ["up", "down"],
               "horizon": {"label": "1w", "steps": 5, "unit": "trading_day"}},
  "reasons": {"pick": {"min": 2, "max": 3},
              "boxes": [{"id": "guidance", "text": "The outlook for next quarter was weaker than expected"}]},
  "confidence": {"min": 1, "max": 5}
}
```

`reveal_view` (trimmed):

```json
{
  "text": "Good results can still mean a falling price. ...",
  "outcome": {"direction": "down", "change": -8.0, "unit": "%", "flat_band": null, "steps": 5},
  "truth": null,
  "stimulus": [{"kind": "chart", "cutoff": "2024-04-25",
                "series": [{"label": "Company X", "name": "Synthetic listed company (fictional)",
                            "unit": "index (cutoff = 100)",
                            "points": [{"t": 0, "v": 100.0}, {"t": 1, "v": 98.06}]}]}],
  "reasons": [{"id": "guidance", "weight": 1.0, "explain": "Prices look ahead. ..."}],
  "sources": [],
  "show": ["outcome", "per_box_explain", "sources", "truth"]
}
```

How to render:
- **Points.** `t` counts observations from the cutoff (0 = day X; negative =
  before). The question has `t ≤ 0` and the reveal has `t ≥ 0`, so the reveal
  continues the line from day X. When dates are not hidden, each point also
  has `d` (ISO date) and `x_unit` is `date`.
- **Units.** `index (cutoff = 100)`: the value on day X is 100. `%` or `% y/y`:
  real levels (yields, inflation).
- **`synthetic: true`.** Show a visible "synthetic data" label. This is
  required by the data rules.
- **`attribution`.** Show it as credits under the chart (`source`,
  `licence`).
- **Several series.** The first series is the one the question is about.
  Others are context, e.g. an index next to a company.
- **Reasons.** Enforce `pick.min` to `pick.max` before submitting.
- **Reveal.** Show `outcome` (direction and change), then each box's
  `explain`, ordered or coloured by `weight`: positive means relevant,
  0 irrelevant, negative wrong or hindsight.
- **Texts.** The views return plain strings in the requested `lang`, falling
  back to English.

## Content authors

Copy `backend/content/nodes/_TEMPLATE.yaml`. Each field is commented there.
The key ones:

| Field | Meaning |
|---|---|
| `id` | `<node in lower case>.m<n>`, e.g. `d1.m1` (checked) |
| `variant` | `day_x` (graded on reasons only), with `truth: none` |
| `content_version` | bump on any change that affects scoring |
| `reviewer` | required before the task goes live |
| `brief` | only what was known on day X; no hidden names, no hindsight words |
| `stimulus[0]` | the chart: `cutoff` (day X), `hide: [name, dates]`, `series` with `series_id`, `from`, `to`, `transform`, `label` |
| `response` | `options`, `horizon` (`1d 1w 2w 1m 3m 6m 1y` or a number), `flat_band`, `expected` |
| `reasons` | `pick: {min, max}` and 6-8 `boxes` with `id`, `text`, `weight` (−1..1), `explain` |
| `sources` | ids from `backend/content/sources.yaml` (checked; `to_check` licences warn) |
| `reveal.text` | the takeaway; no exact numbers (the app shows the real change) |
| `reveal.show` | optional; what the reveal screen shows, from `truth`, `outcome`, `per_box_explain`, `sources` (default: all) |

Rules the build enforces:
- **Hidden names.** When a chart hides names, the series' real name and
  aliases must not appear in visible text.
- **Hindsight words** ("would later", "turned out", "crashed", ...) are
  errors, with two exceptions.
  - Boxes with a negative weight are hindsight traps on purpose.
  - Fields listed in a task's `hindsight_ok`, for example `[brief]`, when
    the word states a fact already known on day X (a crash that had
    happened).
- **Box weights.** At least one box must have a positive weight.
- **Direction check.** `expected` must match the data.
- **`flat_band`.** The default depends on the horizon for `index100`
  (1d 1 %, 1w 2 %, 1m 3 %, longer 5 %). For `level` and `yoy` series, set it
  yourself in the series' unit (e.g. `0.05` = 0.05 pp).
- **Dates.** `valid_until` must not be in the past.

**Transforms.**
- `level`: the raw values.
- `index100`: rebased so day X = 100. Use it for prices.
- `yoy`: change in % against one year earlier. Use it for price levels such
  as a CPI index.

### Adding a real series

1. **Download** the data once into `backend/data/series/series.csv`, one row
   per observation (`series_id,date,value,source,licence`). Use only sources
   cleared in task_engines.md, "Data series and licences".
2. **Add a catalog entry** in `series/catalog.yaml` with `name`, `unit`,
   `frequency` (`daily` or `monthly`), `source`, `licence` and
   `display: false`.
3. **Do the licence checklist** in task_engines.md. Then set
   `display: true`. The build refuses series that may not be displayed.
4. **Add attribution:** a row in `backend/data/SOURCES.md`.

**Synthetic series.** Single-company prices are not licensed, so use a
synthetic series instead. It has no CSV rows: a `synthetic` entry in the
catalog generates a fixed path with a planted move. The parameters are
`anchor`, `start`, `move`, `horizon`, and optionally `mode`, `vol` and
`seed`. See the catalog comments.

## Developers: adding a kind

Each part is a registry in `medium/parts.py`. To add a kind, write one class
with the same methods as the existing kind of that part, then register it.
Nothing else changes.

| Registry | Methods | Example to copy |
|---|---|---|
| `STIMULI` | `validate(spec, store, report)`, `hidden_words(spec, store)`, `compile(spec, store, report, ctx) -> (public, private)` | `ChartStimulus` |
| `RESPONSES` | `validate(spec, report)`, `public(spec, ctx)`, `outcome(spec, ctx, report)`, `check(spec, value)`, `score(spec, value, truth)` | `DirectionResponse` |
| `TRUTHS` | `resolve(spec, outcome)` | `NoTruth`, `OutcomeTruth` |

- `public` goes into the question; `private` into the reveal.
- `ctx` is shared during compilation. For example, the chart puts its first
  series there, so the direction response can measure the outcome.
- After adding a kind, add it to the `enum` in
  `schemas/medium_tasks.schema.json` and add a test in
  `backend/data/tests/test_medium.py`.

## Choices not fixed by the spec (please review)

1. **Node files** follow the format in skills_tree.md (`node`, `panel`,
   `title`, `after`, ...). Medium tasks are listed under `medium:`, and the
   loader ignores the other keys, so cards and easy items live in the same file.
2. **Series metadata.** The spec's table is `series/series.csv`. Units,
   frequency, display permission and synthetic parameters are in a separate
   `series/catalog.yaml`.
3. **Chart fields.**
   - `hide: [name, dates]` and a per-series `label`, used when the name is
     hidden.
   - `series[0]` is the series the question is about.
4. **Direction fields.**
   - `expected`: a fact-check against the data.
   - `flat_band`: the threshold for "flat".
   - `horizon`: how far after day X the outcome is measured.
5. **The truth kind `outcome`** scores the direction for tasks that are not
   day X.
6. **Hindsight boxes.** Boxes with a negative weight, and fields listed in
   `hindsight_ok`, are exempt from the hindsight-word check.
7. **Box count.** 6-8 boxes is a warning, not an error, so short drafts can
   be built.
