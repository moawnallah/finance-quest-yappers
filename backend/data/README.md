# backend/data

Data series and the medium task engine. Owner: Yurii. Guide: [docs/medium_engine.md](../../docs/medium_engine.md).

- Download once and store as one file per series in `series/data/<series_id>.csv`; never call live sources during the demo.
- Sources: only those cleared in [docs/task_engines.md, "Data series and licences"](../../docs/task_engines.md#data-series-and-licences) (GUS, NBP, Ministry of Finance, Eurostat, ECB, OECD, Damodaran, Shiller). Not GPW, MSCI, stooq or Yahoo Finance.
- Single-company prices are not licensed: use a synthetic series, labelled as such on screen.
- Credit each source on screen and in `SOURCES.md`.

## Easy engine (cards and quiz items)

Guide: [docs/easy_engine.md](../../docs/easy_engine.md). Item kinds `single`, `multi`, `true_false`, `numeric` and `reflection`; cards with links from `backend/content/sources.yaml`; the prerequisite test from each node's `after` nodes.

```bash
cd backend/data
python -m easy.build --strict      # -> output/easy.json and output/easy_qa.md
```

Shared helpers for both engines (texts, tolerance rule, node loading) are in `common.py`.

## Medium engine ("estimate and explain")

Spec: `docs/task_engines.md`. Implemented so far: the **chart** stimulus, the **direction** response and the truths **none** (day X, graded on reasons only) and **outcome**. Other kinds (offer, table, number, calculator, ...) are added as one class each in `medium/parts.py`.

```
../content/nodes/<NODE>.yaml     node files; medium tasks under `tasks:` (copy _TEMPLATE.yaml)
series/data/<series_id>.csv      one file per real series: date, value (source, licence in catalog.yaml)
series/catalog.yaml              per series: name, unit, frequency, licence, display, synthetic parameters
SOURCES.md                       attribution list
medium/                          series.py (table, transforms), parts.py (registries), task.py, build.py
schemas/medium_tasks.schema.json contract for output/medium_tasks.json
```

```bash
cd backend/data
pip install -r requirements.txt
python -m medium.build --strict    # -> output/medium_tasks.json and output/medium_qa.md
python -m pytest tests
```

Backend usage:
```python
from medium import load_records, question_view, reveal_view, score
tasks = load_records()
question_view(tasks[tid], lang="en")                       # GET /tasks/{id}: no truth, weights or explanations
score(tasks[tid], "down", ["guidance", "capex"], confidence=4)   # POST /answers: attempt-record fields
reveal_view(tasks[tid])                                    # return with the score
```

The live Day-X tasks use real series (I2: GUS CPI and the NBP reference rate; P4: the OECD share price index for Poland), listed in `series/catalog.yaml`. The old synthetic samples (D1, D3) are now test fixtures in `tests/fixtures/nodes/`.

## Hard engine and simulation core

Guides: [docs/hard_engine.md](../../docs/hard_engine.md) (block language, Blockly, scoring) and [docs/market_sim.md](../../docs/market_sim.md) (market paths, portfolio). `sim/` is the simulation core: `household` and `market` (synthetic, replay, bootstrap, fictional) plus `portfolio`. `series_store.py` (the kernel's series store) feeds both the medium charts and `sim.market`. `hard/` checks, converts (Blockly) and runs block programs; tasks live under `hard:` in the node files.

```bash
python build.py --strict      # easy + medium + hard -> output/*.json and QA reports
python -m pytest tests
```
