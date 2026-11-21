# Demo plan: two paths, milestones, data

Readers: the whole team. Purpose:
- what we show on Sunday;
- what each of us builds, and by when;
- what data we still need.

Status: draft, 2026-11-20.

## What the jury sees (3 minutes)

The same app and the same skills tree, with two people entering it at
different places.
1. **Young adult (27).**
   - Under a month of savings, no investments, wants to start investing.
   - Goes S1 → I1 → I2 → I4 → P1.
   - Learns safety first, then risk, then bonds, then mixing.
2. **Self-directed investor (35).**
   - Holds funds, answers all 5 EU questions correctly, very confident.
   - The router marks the basics as "probably known" (2-item test-outs) and
     sends them to I4 → I5 → P1 → P4.
   - The investor learns costs, then discipline in a crash.

I4 and P1 appear on both paths: the same node, reached from two starting
points. That is the "all generations and levels" claim, shown rather than
told.

| Moment | Young adult | Investor | Feature shown |
|---|---|---|---|
| Survey (EU questions) | 3 of 5, high confidence on two wrong answers | 5 of 5 | Benchmark vs Poland; confidence next to knowledge |
| Path | S1 → I1 → I2 → I4 → P1, each with a reason | test-outs, then I4 → I5 → P1 → P4 | Explainable router |
| Medium task | I2: day X, early 2022, CPI and the NBP rate rising; choose deposit, fixed or indexed bond, give reasons | P4: day X, end of March 2020, after the crash; give reasons, then see what happened | Grading of reasons, outcome shown separately |
| Tutor | Two free hints, then "explain more simply" | After submission: why a good decision can still have a bad outcome | Guarded tutor, no answer before submission |
| Hard task | S1: a buffer rule tested on 1,000 futures | P4: a rebalancing rule tested on crashes | Score 51-100 and histogram (one of the two, see M4) |
| End | Confidence before and after | Calibration gap shrinks | Measurement |

**Flow in the app** (built 2026-11-21, API only):
1. Survey.
2. The path, or "not ready yet, choose one of the two".
3. The nodes.
4. The end-of-path check-in.
5. Thanks, with optional feedback and "try the other path".

Details: docs/admin_and_profile.md, "Demo mode and the end of a path".

## Paths in detail

### A. Young adult

| Step | Node | Content | Status |
|---|---|---|---|
| 1 | Survey | 12 answers (docs/onboarding_router.md) | router in code with tests (2026-11-21); survey screen and API wiring left |
| 2 | F1 | 2-item test-out (prerequisite of S1) | items to write |
| 3 | S1 Emergency fund | 4 cards; easy items; medium: a persona's 24-month balance, estimate the buffer in months; the hard task moved to the P1 capstone (2026-11-21) | cards draft; rest to do |
| 4 | I1 Risk as a spread | 3 cards; easy; medium: histogram of yearly returns, estimate losing years and the worst year | cards draft |
| 5 | I2 Deposits and bonds | 4 cards; easy; medium: day X early 2022 (choice + reasons) | cards draft; medium built on real data (i2.m1) |
| 6 | I4 One stock vs an index | 2 cards; easy | cards draft |
| 7 | P1 Diversification | 3 cards; easy; optional medium: estimate the 2008 result of a 50/50 mix; **hard: capstone "Ania's first two years" (p1.h1: buffer, bills pot, card, fund vs bond vs one company), built 2026-11-21; optional on the investor path** | cards draft; hard draft |

### B. Self-directed investor

| Step | Node | Content | Status |
|---|---|---|---|
| 1 | Survey | the same 12 answers | as above |
| 2 | F1, F2, F3, S1, I1 (and others the router marks known) | 2-item test-outs | items to write |
| 3 | I4 | shared with path A | cards draft |
| 4 | I5 Funds and costs | 4 cards; easy; medium: two KIDs with 2% and 0.3% costs, estimate the difference after 20 years (calculator) | cards draft |
| 5 | P1 | shared with path A | cards draft |
| 6 | P2 Allocation by horizon | 3 cards; test-out (prerequisite of P4) | cards draft |
| 7 | P4 Rebalancing in a crash | 3 cards; easy; medium: day X March 2020 on a real monthly index; **hard: "Marek over ten years" (p4.h1 v2: moving target, minimum fee, 19% tax; built 2026-11-21, fictional market until the data is in)** | cards and hard draft; medium built on real data (p4.m1) |

## Milestones

Each has an owner and a "done when" check.

| # | When | Milestone | Owner | Done when |
|---|---|---|---|---|
| M1 | Sat 10:00 | **Content for 8 nodes.** Cards reviewed; 3-4 easy items per node, each with `check: true` where it feeds a test-out; test-out items for F1, F2, F3, S4 | Claude drafts, Mateusz reviews (+ second AI check) | Every card and item has a reviewer; `kb.ingest` accepts them |
| M2 | Sat 12:00 | **Router in code** (`backend/ml/router`): survey scoring as in EB525, ability, mastery, needs, priority, path, challenges, `reco_events`. **Done 2026-11-21**; left: `POST /onboarding` in the API and the survey screen | Mateusz (code), Mohamed (API), Michał (screen) | The two demo personas get exactly the paths above, in tests |
| M3 | Sat 14:00 | **Medium tasks on real data** for I1, I2, I5, P4. Engine kinds needed beyond chart + direction: `number` response with `calculator` truth (I1, I5, P1), `choice` response (I2) | Yurii (engine and data), Mateusz (task text) | `python -m medium.build --strict` passes with no synthetic series on the demo paths |
| M4 | Sat 18:00 | **One hard task** in the block engine, on the shared simulation core `sim/`. **S1 "Ania's buffer rule" engine and content done 2026-11-21** (docs/hard_engine.md); the Blockly screen is left | Mateusz (engine), Michał (screen) | Reference program accepted, known-bad rejected, score shown with a histogram that includes baseline bots |
| M5 | Sat 18:00 | **Tutor on a real model** at Mo's machine | Mateusz, Mohamed | `python -m eval.run --set model_choice`: at least 18 of 20 pass the checks, about 10 s per answer; the red-team run has been read |
| M6 | Sat 22:00 | **Backend and app wired** for both paths: survey → path → node → tasks → tutor; admin "advice watch" view | Mohamed, Michał | Both personas can click through from start to finish on the demo machine |
| M7 | Sun 09:00 | **Freeze**: `PROMPT_VERSION`, content versions; tutor answers for the demo script generated and reviewed in advance | all | A clean run of the 3-minute script with the model switched off (stored answers) |
| M8 | Sun 11:00 | **Hallway test** (8-15 people): confidence before and after one mission; rehearsal | Mateusz, pitch owner | n, the before/after numbers and a "not a controlled trial" note go on a slide |

## Router status (2026-11-20)

- **Designed:**
  - the survey, built on EB525 Q1-Q9;
  - item difficulties fitted to the Polish shares;
  - the same prior for everyone (demographic priors dropped 2026-11-20);
  - need rules, priority and path selection;
  - test-outs.
- **Checked** in a scratch simulation and on 5 hand-written personas
  (RESEARCH.md; docs/onboarding_router.md).
- **In code since 2026-11-21:** `backend/ml/router`, with the four
  personas as tests and `reco_events` rows. Left: the API route and the
  survey screen.
- **Licence:** EB525 is under the European Commission reuse notice
  (Decision 2011/833/EU), so we may reuse the questions and the Polish
  tables with credit and without distorting the meaning.
- **Open:**
  - the English master wording of Q1-Q9, to be copied from the report;
  - the official scoring of "don't know", which counts as wrong.

## Data we need (for Yurii)

All series go into `backend/data/series/series.csv` with the columns
`series_id, date, value, source, licence`, plus one entry in
`series/catalog.yaml` with `display: true` once the licence is noted.
Download by hand, once. No bulk or automated downloading from NBP.

| Series | For | Source | Frequency, period | Licence | Notes |
|---|---|---|---|---|---|
| CPI, % y/y (Poland) | I2 day X, F2 | GUS (Knowledge Databases or the CPI page) | monthly, 2019-2025 | CC BY 4.0 | The headline index, previous year = 100, converted to % y/y |
| NBP reference rate | I2 day X, L2 later | NBP | each change (decision dates), 2019-2025 | NBP regulamin: credit "Source: NBP, www.nbp.pl" | A step series; store each decision date and the new level |
| Equity index, monthly | P4 day X (March 2020), I4 index line | OECD share prices, Poland (FRED SPASTT01PLM661N, or the OECD Data Explorer) | monthly, 2015-2025 | OECD CC BY 4.0 | Price index (2015 = 100), not total return; say so on screen |
| US stocks, bonds, bills, yearly | I1 histogram, P1 2008/2022, P2 | Damodaran, histretSP | yearly, 1928-2025 | attribution | Already read; total returns, nominal |
| Monthly S&P composite (backup for P4) | P4 | Shiller, "U.S. Stock Markets 1871-Present" | monthly, 2019-2021 | attribution | Monthly averages of daily closes |
| Long-term government bond yield, Poland | P1 later, D3 | OECD (or Eurostat) | monthly | CC BY 4.0 | Only if P1 gets a Polish version |
| HICP, Poland and EU | backup for CPI | Eurostat | monthly | EC reuse | Only if GUS is inconvenient |

**Not needed:**
- retail bond rate history: obligacjeskarbowe.pl does not allow commercial
  reuse. Bond terms are stated as rules, with illustrative numbers;
- single-company prices: synthetic, labelled.

**Headlines for day X** (I2 early 2022, P4 March 2020) are written by us in
neutral words, using only what was known that day. Press archives are
licensed.

## Fallbacks

| If | Then |
|---|---|
| The model is slow or down | Stored answers for the script; `TUTOR_ENABLED=false` still leaves a working app |
| The hard engine is not ready | Show the medium tasks and the histogram mock-up; say "next" in the pitch |
| A real series is missing | Use the synthetic series, labelled "synthetic" on screen |
| The router is not wired | Hard-code the two persona paths behind the survey screen, and say so if asked |
