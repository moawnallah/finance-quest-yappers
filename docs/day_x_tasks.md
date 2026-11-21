# Demo content: nodes, Day-X tasks and real data

Readers: the whole team. Status: draft, 2026-11-21 (Yurii, with Claude). Reviewer: none yet.

What this change does:
- trims the content to the nodes on the two demo paths;
- adds one Day-X task each for I2 and P4, on real data;
- adds the `choice` response kind to the medium engine;
- loads the first three real series.

## 1. Nodes

The demo paths (docs/demo_plan.md) use **11 nodes**: F1, F2, F3, S1, I1, I2, I4, I5, P1, P2, P4.
Only these have files in `backend/content/nodes/`.

| Removed | Where it went | Why |
|---|---|---|
| D1, D3 | `backend/data/tests/fixtures/nodes/` | Not on a demo path. They are the engine's test samples (synthetic data), so the tests now build from the fixtures. |
| S4 | deleted | Not on a demo path. |

All 32 nodes stay in `backend/ml/router/tree.yaml`, so the app can show the others as present but locked.
**Note for the app:** P2 has `after: [P1, S4]`, and S4 has no content. P2 must not stay locked because of S4.

## 2. The two Day-X tasks

Both are `variant: day_x` with `truth: none`. The user sees a chart cut at day X and makes a **decision**
(`choice`), picks 2-3 reasons and rates confidence. **Only the reasons are graded**; the choice is stored. The reveal
shows the rest of the chart and names the date. The views contain no real names or dates before the answer
(`hide: [name, dates]`; the build checks names, aliases and hindsight words).

### i2.m1: deposit or bond, 16 February 2022
- **Persona:** Kasia, 28, has 20,000 PLN for a flat deposit in about 4 years and a separate emergency fund.
- **Chart:** inflation (% y/y) and the central bank rate, monthly from Jan 2019. The cutoff is January 2022 (9.4% and 2.25%);
  the reveal runs to Dec 2025, with the 18.4% peak in Feb 2023 and the rate up to 6.75%.
- **Known on day X:** five rate hikes since October (the last on 9 Feb); VAT cuts on food, fuel and energy from 1 Feb to
  31 Jul 2022. January's CPI was published on 15 Feb (GUS publishes no January flash), which is why day X is 16 Feb and not
  1 Feb. It is also before 24 Feb.
- **Options:**
  - a 12-month deposit renewed each year;
  - a 3-year fixed-rate bond, then a 1-year deposit (no 4-year fixed retail bond exists);
  - a 4-year inflation-indexed bond.
- **Best reasons:** inflation is above every rate on offer (1.0); the indexed bond follows prices (0.8); rates are rising, so
  deposits get renewed at higher rates (0.6).
- **Traps:** "a fixed rate is safest" (−0.3); "inflation will pass 15%" (hindsight, −1.0).
- **Bond terms** are rules in our own words, with no real rates (obligacjeskarbowe.pl data may not be reused).

### p4.m1: sell, hold or rebalance, 31 March 2020
- **Persona:** Marek, 35 (the same person as the hard task p4.h1), retirement 20+ years away, target 60/40 shares/bonds.
- **Chart:** the Polish share price index (OECD, monthly, rebased to 100 at day X) from Jan 2018. The fall from
  February to March is −23.8%, so 60/40 has become about 53/47. The reveal runs to Dec 2021: back at the February level by Dec 2020.
- **Known on day X:** the pandemic; schools and borders closed; the NBP cut to 1.00% and started buying bonds; the government
  announced aid.
- **Options:** sell / hold / rebalance to 60/40 / all into shares.
- **Best reasons:** a long horizon (1.0); a rule set in calm times (0.8); you can't time the bottom (0.6).
- **Traps:** "the news is frightening" (−0.5); "prices will be back within a year" (hindsight, −1.0).
- **Related card fix:** card p4.c2 and the feedback on item p4.e3 now use **2008/2009** instead of 2020, so the cards don't give away
  the outcome of this task.

Why `choice` and not up/down: the specs ask for a decision ("pick a deposit or a bond"; "sell or hold?"), and P4's
lesson is that a rule beats a forecast. The chart is still the centre of the screen, before and after the answer.

## 3. Engine change: response `choice`

`backend/data/medium/parts.py`, `ChoiceResponse`, registered in `RESPONSES`.

```yaml
response:
  kind: choice
  options:
    - {id: deposit, text: "A 12-month bank deposit, renewed each year"}
    - {id: indexed, text: "..."}
```

- **Question view:** `{"kind": "choice", "options": [{"id", "text"}]}`. **Frontend: needs a widget** (one option, then reasons).
- **Scoring:** 1/0 against the truth when one exists. For day X there is no truth: `score_estimate` is null and the score is the reasons
  score. `reveal.outcome` is null; what happened is in the reveal chart.
- **Validation:** at least 2 options, unique lowercase ids, text on each. Option texts are checked for hindsight words and hidden names.
- Added to the schema enum; tests are in `tests/test_medium.py`.

## 4. Data

| series_id | What | Source and download | Rows | Licence (checked 2026-11-21) |
|---|---|---|---|---|
| `gus_cpi_pl_m` | CPI, % y/y: GUS "same month previous year = 100" − 100, final values | GUS table "Miesięczne wskaźniki cen … od 1982 roku", CSV | 2019-01 to 2025-12 (84) | stat.gov.pl/copyright: reuse with the source given |
| `nbp_ref_rate_m` | NBP reference rate in force on the last day of each month | `static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml` (effective dates) | 2019-01 to 2025-12 (84) | NBP website terms: "Source: NBP, www.nbp.pl" |
| `oecd_share_prices_pl_m` | Share price index Poland, 2015 = 100, monthly average, no dividends | OECD SDMX API, `DSD_STES@DF_FINMARK`, `POL.M.SHARE.IX` | 2005-01 to 2025-12 (252) | CC BY 4.0 (OECD default) |

- Downloaded once, on 2026-11-21. The raw files are not committed. `backend/data/series/import_demo_series.py` lists
  the exact URLs and rebuilds `series.csv` from them.
- **FRED is not used.** It carries the same OECD series, but its terms forbid commercial redistribution without permission.
- Attribution rows are in `backend/data/SOURCES.md`; the source register entries are `gus_cpi`, `nbp_ref_rate` and
  `oecd_share_prices_pl` in `backend/content/sources.yaml`.
- **Licences checked** by Yurii on 2026-11-21 (docs/task_engines.md checklist), so `display: true` for all three.
  `python build.py --strict` builds both tasks; they are ⚠️ only because there is no reviewer yet, so `live` stays false.

## 5. To do before the demo

| What | Who |
|---|---|
| Review the text of i2.m1 and p4.m1, and the reason weights; set `reviewer` | Mateusz |
| Retarget the tutor eval sets (`ml/eval/model_choice.yaml`, `red_team.yaml`) from d1.m1/d3.m1 to i2.m1/p4.m1, **before** the rebuilt `medium_tasks.json` is pushed | Mateusz (done 2026-11-21) |
| Router: the investor path is I4 → I5 in the tests; the demo plan says I4 → I5 → P1 → P4 | Mateusz (done 2026-11-21: demo mode extends I4 → I5 to the investor path, `router/demo.py`) |
| `choice` widget; P2 must not be locked by S4; show `attribution` under the charts | Michał, Mohamed |
| F1, F2 and F3 have no cards (someone who fails a test-out lands on an empty node) | content |
