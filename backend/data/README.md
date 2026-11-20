# backend/data

Data series and the medium task engine. Owner: Yurii. Guide: [docs/medium_engine.md](../../docs/medium_engine.md).

- Download once and store as rows in `series/series.csv`; never call live sources during the demo.
- Sources: only those cleared in [docs/task_engines.md, "Data series and licences"](../../docs/task_engines.md#data-series-and-licences) (GUS, NBP, Ministry of Finance, Eurostat, ECB, OECD, Damodaran, Shiller). Not GPW, MSCI, stooq or Yahoo Finance.
- Single-company prices are not licensed: use a synthetic series, labelled as such on screen.
- Credit each source on screen and in `SOURCES.md`.

## Medium engine ("estimate and explain")

Spec: `docs/task_engines.md`. Implemented so far: the **chart** stimulus, the **direction** response and the truths **none** (day X, graded on reasons only) and **outcome**. Other kinds (offer, table, number, calculator, ...) are added as one class each in `medium/parts.py`.

```
../content/nodes/<NODE>.yaml     node files; medium tasks under `tasks:` (copy _TEMPLATE.yaml)
series/series.csv                the series table: series_id, date, value, source, licence
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

The samples (D1, D3) use synthetic series, because no real series has passed the licence checklist yet.
