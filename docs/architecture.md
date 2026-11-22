# Architecture: engines, simulation core, services

Readers:
- everyone who adds an engine, a task kind, a mode or an endpoint;
- first of all, Yurii before the hard engine and Mohamed for the API.

Purpose: one picture of how the parts fit, and the rules that keep them
working as we add more (hard tasks, sandbox, historical replays).

Status: draft, 2026-11-21. Today's code is listed under "From today to the
target".

## Principles

1. **Content is data.**
   - Tasks, cards, items and scenarios are YAML in `backend/content/`.
   - No logic lives in content, and no content lives in code.
2. **One contract per engine, one shared kernel.**
   - Engines share helpers through the kernel.
   - They never import each other, and they are never copied to make a new
     one.
3. **One simulation core.**
   - Hard tasks, the sandbox and historical replays use the same simulator.
   - They differ only in how they use it.
4. **Dependencies point down only:** content → kernel → simulation core →
   engines → API → app.
5. **Everything is versioned** and the version is stored with every
   attempt: `schema_version`, `content_version`, `engine_version`.
6. **Safety by construction.**
   - Answers, truth values and weights never reach the browser, or the
     tutor model, before submission.
   - This is enforced by the data each layer is given, not by instructions.

## Target layout

```
backend/
  content/                 authored YAML: nodes/ (cards, items, medium, hard), sources.yaml,
                           wheel/ (product slices), scenarios/ (named crises, replay episodes)
  data/
    common.py              kernel: texts and languages, tolerance rule, ids, source register,
                           the Engine protocol, Report (errors and warnings)
    series_store.py        the series store (kernel; moved from medium/ on 2026-11-21 so sim/ can use it)
    series/                its data: catalog.yaml + data/<series_id>.csv (source, licence, display)
    sim/                   simulation core (below)
    easy/  medium/  hard/  engines, all with the same interface
    build.py               one build: every engine -> output/*.json + one QA report
    output/                compiled artifacts the API serves
    schemas/               JSON schemas: the contracts between engines, API and app
    tests/
  ml/
    tutor/                 the tutor agent (docs/tutor_agent.md)
    router/                survey scoring, router, BASAL client (docs/onboarding_router.md)
    eval/                  model choice and red-team sets; api_run.py runs them through the deployed /tutor
    experiments/           basal_shadow/: BASAL against the router on the test personas
  api/                     FastAPI (Mohamed): routes, engine registry, database, admin
frontend/                  Flutter (Michał): one renderer per task kind, tree, wheel, tutor
```

## The engine interface

Every engine implements the same protocol, kept in `common.py`.

```python
class Engine(Protocol):
    level: str                                       # "easy" | "medium" | "hard"
    def validate(self, spec: dict) -> Report: ...    # content checks; errors block the build
    def compile(self, spec: dict) -> dict: ...       # -> record {question, reveal, meta}
    def question_view(self, record: dict, lang: str) -> dict: ...  # safe before the answer
    def score(self, record: dict, answer: dict) -> dict: ...       # -> attempt fields, score 0-1
    def reveal_view(self, record: dict, lang: str) -> dict: ...    # after the answer
    def secrets(self, record: dict) -> dict: ...     # truth values and correct texts, for the tutor's leak check
```

- **The record** always has three blocks:
  - `question`: may be sent before the answer;
  - `reveal`: sent only after the answer;
  - `meta`: internal; never sent.
- **The API holds one registry**, `ENGINES = {"easy": ..., "medium": ...,
  "hard": ...}`. `GET /tasks/{id}` and `POST /answers` look up the engine
  by the record's level. The API never knows how an engine works inside.

## The simulation core (`sim/`)

Two halves with one stepping loop. A feature uses one half or both.

| Part | What it is |
|---|---|
| `sim/market`: price paths | Assets (shares, bonds, cash, gold, fictional companies) and their monthly or daily returns. **Path sources:** **replay** (one real path from the series store, with checkpoints that show only what was known then); **futures** (block bootstrap of real history, with a seed); **fictional** (a regime model and an event generator: "Company X loses its CEO", "inflation surprise"; calibrated on real data, labelled fictional) |
| `sim/household`: the ledger | `State`: cash, buffer, debts, holdings, income, costs, goals, age. Modules: income and job loss, expense shocks, inflation, interest rates, fees, tax. **Override** events, such as "job loss in month 4" |
| `Policy` | A function from state to actions. A compiled block program is one policy; a sandbox portfolio rule is another; baseline bots are policies too |
| Metrics | Minimum balance, end wealth (real), maximum drawdown, goal reached, months in debt |
| `run(state, policy, scenario, months, seed)` | The only entry point; deterministic for the same inputs |

**Who uses it, and how:**

| Feature | Uses `sim` as | Scoring |
|---|---|---|
| Hard engine | Compiles blocks to a `Policy`. Obligatory tests are overrides; optional tests are probability-weighted scenarios | 51-100, histogram (docs/task_engines.md) |
| **Past markets ("time machine")** | `sim/market` replay of a real episode (2008, March 2020, 2022) with checkpoints; the user holds or changes a portfolio at each one. The frontend already has a time-machine screen with a sample curve | None, or a medium day-X task on the same episode |
| **Sandbox = our fictional market** | `sim/market` fictional paths with generated events; the user builds and manages a portfolio of fictional assets; friends can play the same seed. No money, prizes or exchangeable points | None (later: a weekly challenge on a shared seed) |
| Free play (later) | Both halves: a whole financial life (job, shocks, goals, markets). Hardest to verify, because many outcomes have no single right answer | None |
| Medium calculators | Simple calculators stay pure functions. Ones that need a path (P3 lump sum vs instalments) call `sim.run` | Medium rules |

## Where a new idea goes

| The idea needs | It is | Example | Work |
|---|---|---|---|
| A new thing to show or answer inside an existing answer cycle | a new **kind** in an engine's registry | medium `number` response, `calculator` truth, `offer` stimulus | One class, its tests, the schema |
| A new answer cycle (what the user submits, how it is scored) | a new **engine** | hard: the user submits a program | A package implementing `Engine`, plus a schema |
| A new world mechanism | a new **module** in `sim/` | mortgage with a variable rate, PPK contributions | One module class and its golden test |
| A new way to use the simulator without scoring | a new **service or mode** | sandbox, replay | An API route on top of `sim.run` |
| New learning content | **content** only | a new node, a new crisis episode | YAML; the build validates it |

If an idea fits none of these rows, write down why before building it.

## Contracts and tests

| Check | What it catches | Where |
|---|---|---|
| JSON schema of every artifact (`output/*.json`) | An engine output the API or app cannot read | Engine tests; the API's tests load the same schemas |
| Golden tests per task | A content or engine change that silently changes a result: the reference answer passes, a known bad answer fails | Built from content (hard: `reference_program`, `known_bad_programs`) |
| Property tests | Scores outside 0-1; a better answer scoring lower; non-determinism for the same seed | Kernel and engine tests |
| No-leak tests | Truth or weights in `question_view` or in the tutor's context before submission | Engines and tutor (both exist) |
| Strict build | A task with errors reaching `output/` | `python -m build --strict` in CI |
| CI on Linux **and** Windows | Encoding and path bugs (the cp1250 crash we had) | CI matrix |

**Versioning.**
- Any content change that affects scoring bumps `content_version`.
- Any engine change that affects scoring bumps `engine_version`.
- Attempts store both, so old scores stay interpretable and histograms are
  per version.

## Ownership

| Package | Owner | Reviews changes to |
|---|---|---|
| `backend/content` | content authors (Mateusz reviews) | facts, sources, licences |
| `backend/data/common.py`, `series/`, `sim/` | Yurii | the kernel, because everything depends on it |
| `backend/data/easy`, `medium`, `hard` | Yurii | engines |
| `backend/ml` | Mateusz | tutor, router, eval |
| `backend/api` | Mohamed | routes, registry, database, admin |
| `frontend` | Michał | renderers |

Later this table becomes a `CODEOWNERS` file. A change to the kernel or a
schema needs a review from the owners of the packages that use it.

## From today to the target

| Today | Step | When |
|---|---|---|
| `easy/`, `medium/` and `hard/` each have their own build | **Done 2026-11-21:** one `build.py` runs all three. **Open:** the `Engine` protocol in `common.py` and an API registry | Before the API |
| Simulator | **Done 2026-11-21:** `sim/household`; `sim/market` with all four path sources (synthetic, replay, bootstrap, fictional) and `sim/portfolio` (multi-asset, rebalancing), see [market_sim.md](market_sim.md). The series store moved into the kernel. Multi-asset household with a target mix and rebalancing (done 2026-11-21). **Open:** real series in the store | Data first |
| Hard engine | **Done 2026-11-21 for S1 and P4** ([hard_engine.md](hard_engine.md)): block language with `rebalance`, Blockly definitions, toolbox and converter, golden checks in the build, two-dimensional score (resilience × growth), futures, bots. **Open:** real data for P4, the JSON schema, API wiring | M4 |
| Router | **Done 2026-11-21:** `backend/ml/router` (tree.yaml, benchmarks.yaml, router.py), the persona tests, `reco_events` rows. **Open:** `POST /onboarding` in the API | M2 |
| No API code | `backend/api` with the engine registry and the endpoints in skills_tree.md and tutor_agent.md | M6 |
| Time machine, sandbox, free play: not started | Build in this order, one at a time: (1) **time machine** on `sim/market` replay, with real, licensed data and the existing screen; (2) **sandbox** = the same market player with a fictional path source; (3) free play, only if 1 and 2 work | After the demo |

**What not to do:**
- one large file that handles every task type;
- a copy of an engine to make a "slightly different" one;
- an engine importing another engine;
- logic in YAML (conditions, formulas);
- calling live data sources during a request.
