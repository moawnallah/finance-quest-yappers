# Admin panel, user profile, study mode

Readers:
- Mohamed (endpoints, tables);
- Michał (screens);
- Mateusz (the analytics module and the next-step model);
- whoever runs the hallway test.

Purpose: agree what the admin panel and the profile show, where each number
comes from, and what we must log now so that a "what next" model can be
trained later.

Status: proposal for review, 2026-11-21. Nothing here is built yet. The
existing pieces are named where they exist:
- Mo's tables: `users`, `profiles`, `attempts`, `events`,
  `benchmark_answers`, `user_badges`;
- `/admin/ab-results`;
- the tutor's `llm_events` and the router's `reco_events`
  (docs/tutor_agent.md, section 6).

## How it is built

- **Logic lives in one Python package**, `backend/ml/analytics/`. It has
  pure functions that take rows (lists of dicts) and return the numbers
  for a view. They are tested with hand-made rows.
- **The API endpoints** (Mohamed) only read rows from the database, call
  these functions and return JSON.
- **The screens** (Michał) only draw that JSON.

This keeps the numbers testable and lets us change a metric without
touching the API.

**Prerequisite.** A database that survives restarts: hosted Postgres
instead of SQLite in `/tmp`. **This is not done yet** (fix 1 in the
handover). Until then every number below resets on a cold start.

## New tables and fields

| Table or field | Columns | Why |
|---|---|---|
| `reco_events` | from the router (docs/tutor_agent.md, section 6), plus `shown_rank`, `exploration` | Router overview; training data for the next-step model |
| `llm_events` | from the tutor (docs/tutor_agent.md, section 5) | AI overview, advice watch |
| `feedback` | `id, ts, user_pseudo_id, where (item, card, task, tutor_answer, screen), target_id, kind (wrong_fact, unclear, bug, idea, other), text (max 500 chars, masked), status (new, triaged, fixed, wont_fix), resolved_by, resolved_at` | Bug reports and feedback |
| `attempts.duration_ms` | engine time to check, convert and score | Hard-task timing |
| `attempts.points`, `attempts.growth_index` | hard tasks | Hard-task results, percentiles |
| `consents` | `participant_id, consent_version, given_at, withdrawn_at` | Study mode |
| `next_step_events` | below, "Data for the next-step model" | Training data |
| `admin_audit` | `ts, admin, action, target, before, after` | Who changed a kill switch or a report status |

## Admin panel

Access: admin role only, key in a header. Users appear only by pseudonymous
id.

### A. Overview (the landing page)

**Tiles:**
- users today / this week;
- attempts today;
- nodes completed;
- tutor answers and the fallback rate;
- open bug reports;
- active alerts.

**Alerts are listed first.** They come from the views below, for example:
- "item i2.e2: 3 reports";
- "advice check failures above 5% in the last hour";
- "router off by more than 0.2 on node P1".

### B. Questions and tasks (content quality)

**Table of every item and task:** id, node, level, content version,
reviewer, live or draft. Then, from **first** attempts only:

| Metric | How | What it catches |
|---|---|---|
| n | first attempts | Too few answers to judge |
| First-attempt success | mean score | Too easy or too hard for its level |
| Mean confidence | mean p | — |
| Calibration gap | mean p − mean score | Items that make people overconfident |
| Discrimination | correlation of the item score with the user's ability θ | Items that strong users fail (a wrong key or an ambiguous text) |
| Answer distribution | share per option (easy) or per reason box (medium) | Distractors nobody picks; a box picked by most strong users with a negative weight |
| Estimate error | distribution of (answer − truth) / truth (medium numbers) | A tolerance band that is too tight |
| Median time | `submitted_at − started_at` | Unclear or too long |
| Clarity | mean of `clarity_rating` | Unclear wording |
| Hints | share with hints; share with paid hints | Too hard, or a hint ladder that does not help |
| Reports | count from `feedback` | Wrong facts |
| Freshness | `valid_until` within 14 days | Limits and rates going stale |

**Hard tasks get their own panel:**
- acceptance rate;
- the obligatory test that fails most often;
- the distribution of points and of the growth index;
- the scatter of resilience × growth, with the bots;
- median `duration_ms`.

**The "confidence up, success flat" flag** (docs/tutor_agent.md) is shown
here per node.

**Drill-down:** clicking an item shows its text, options, answer key, why,
sources, all of the metrics above, and its reports.

### C. Self-assessment trend

- **Onboarding self-rating** (Q1) vs knowledge score, compared with the
  EB525 Polish table (share rating themselves "high" by score band).
- **Per-item confidence over time:** weekly mean confidence, mean score,
  calibration gap and Brier score (mean of (p − score)²).
- **Confidence before vs after a mission** (`profiles.confidence_before`,
  `confidence_after`), paired per user.
- **Splits:** by age band and by entry path (young adult, investor,
  other). For a single user, see the profile below.
- **What we want to see:** the gap shrinking for users who started
  overconfident.
- **Caveat:** these are descriptive numbers, not proof that the app works.

### D. AI overview (the tutor)

The views from docs/tutor_agent.md, section 6:
- **advice watch:** advice requests, injections, check failures by type;
- **flagged queue** with labelling;
- **quality and cost:** fallback rate, latency p50/p95, tokens, thumbs, by
  model and prompt version;
- **hints and learning.**

Today the model is **Gemma** (Mo's choice), so model and prompt version are
filters here.

### E. Router overview

**Paths and rules:**
- how often each first path is issued;
- how often each need rule fires;
- the distribution of knowledge bands vs EB525.

**Calibration:**
- predicted mastery vs observed first-item success, by decile and by node,
  from `first_item` and `test_out` events;
- challenge pass rates by node.

**Behaviour:** recommendations accepted vs ignored; time to finish the
path.

**Shadow model** (BASAL or another): agreement with the router; the share
below the confidence threshold; Brier of both on the same first items once
there are outcomes.

**Alert:** a node where |predicted − observed| > 0.2 over 30+ users.

### F. Engines and tests

- **Last build:**
  - tasks compiled per engine;
  - errors and warnings from `output/*_qa.md`;
  - content versions live.
- **Tests:** the last CI run per suite (engines, ml, API) with pass and
  fail counts, linked to the run.
- **Hard-task timing:**
  - `duration_ms` p50/p95 per task, split into check and convert vs
    simulate;
  - the build's time per task (golden checks and bots).

  Today one submission takes about 150 ms; alert above 2 s.

### G. Reports and feedback

- **Collecting.** Every item, card, task and tutor answer has "Report a
  problem". The user picks a kind (wrong fact, unclear, bug, idea, other)
  and may add up to 500 characters of text, with personal data masked.
  After a mission the user also gives one 1-5 rating and an optional
  comment.
- **Queue.** Reports are newest first, with filters by kind, node and
  status. Statuses go new → triaged → fixed or won't fix; each change is
  written to `admin_audit`.
- **Auto-flag.** An item with 2 or more open "wrong fact" reports is shown
  as a draft until reviewed (proposal).

### H. Study (hallway test)

- **Participants and consent:** participants, consents given and
  withdrawn.
- **Paired results** (n, mean change, and the count who improved, stayed
  or got worse):
  - confidence before vs after;
  - knowledge score before vs after (EB525 items or check items);
  - calibration gap before vs after.
- **Fixed note:** "Hallway test, n = …, not a controlled trial."
- **Export:** CSV by participant id only.

### I. Data for the next-step model ("what next after the path")

**The question:** when a user finishes the recommended path (or a node),
which node should come next?
- Today the router answers it with rules.
- Later, a model can learn it from data, **if we log the right things from
  day one**.

**One row per decision point** (`next_step_events`):

| Field | Content |
|---|---|
| `ts, user_pseudo_id, router_version` | when, who (pseudonymous), which rules |
| `trigger` | `path_finished` or `node_finished` |
| `state` | mastery per node, calibration gap, needs, goal, horizon, age band, days since start, recent scores, Explore-wheel slices viewed in the last 7 days |
| `candidates` | every node shown as a next option, each with its rank, priority and the rule's reason |
| `shown_rank`, `exploration` | where each candidate was shown, and whether its position was randomised |
| `chosen` | the node the user opened, or none |
| `outcome` | filled later: first-item success in the chosen node, node completed (yes or no), back within 7 days, confidence change |

**Why log the shown candidates and a little randomness.** If we log only
what users chose from the router's own list, a model can only learn the
router back. The fix:
- show the router's top 3;
- with a small probability (proposal: 10%), swap one position for another
  unlocked node, and mark it `exploration: true`.

That gives the model a fair view of alternatives. It also lets us evaluate
a new policy offline before it reaches users, by weighting the logged
outcomes by the chance each option had of being shown.

**When a model makes sense:**
- a few hundred decision points with outcomes;
- first as a logistic regression on "first-item success and completion"
  per candidate;
- compared with the rule router on held-out users, as in
  docs/onboarding_router.md, "Replacing the rules".

**Admin view:**
- dataset size;
- the share of rows with an outcome;
- the exploration rate;
- class balance;
- an anonymised CSV export.

### J. Also worth having

- **A/B results.** Mo's `/admin/ab-results` moves here.
- **Sources and licences.** The source register with licence status
  (`to_check` in red), and cards that cite each source.
- **Kill switches** with the audit log (docs/tutor_agent.md).
- **Data requests.** Delete or export one participant's data by id.

## User profile (what the user sees)

| Section | Shows | From |
|---|---|---|
| Your path | the current recommended path, the goal node, the next suggestion with its reason; challenges available | router output, completion |
| What you know | progress per panel and per node (done, in progress, challenge passed); mastery as 3 bands, not raw numbers | attempts, mastery updates |
| How sure vs how right | a chart over weeks: mean confidence vs mean score; the gap in words ("you are about right", "you tend to be more sure than right"). Badge "Well calibrated" when the gap is under 0.1 over the last 20 answers | attempts (`p`, `score`) |
| You and Poland | your EB525 knowledge score vs Poland and your age group | router `benchmarks` |
| Hard tasks | points and growth index per task, the percentile on each axis, the best rule (view in Blockly) | attempts |
| Activity | weekly streak, missions finished, tutor questions left (the streak adds quota) | attempts, events |
| Your data | what is stored and why; download; delete; study participation and withdrawal | consents, all tables by user id |

**Mastery after onboarding:** the router's starting value, then one update
per first attempt: θ_k ← θ_k + K · (score − P(success)), with K = 0.4
(proposal). This is the two-sided Elo from the research notes: item
difficulty updates too, once there are enough users. The profile shows
bands: below 0.6 "learning", 0.6-0.8 "solid", 0.8 and above "mastered".

**Contract:** `GET /me/summary` returns `path`, `goal`, `challenges`,
`panels` (each with nodes and their state and band), `calibration` (gap,
Brier, weekly series), `benchmarks`, `hard` (per task: points,
growth_index, percentiles), `activity` and `privacy`.

## Study mode: consent and anonymous ids

**Before the hallway test**, the app shows:

> We are testing a student project at Collabothon. We record your answers,
> how sure you were, and how long you took, under a random code. We do not
> record your name or contact details. You can stop at any time, and ask us
> to delete your answers using your code.
>
> [ ] I agree to take part.

- **Participant id:**
  - a random code shown to the participant, e.g. `FQ-7K3P`;
  - 4 characters from an alphabet without 0, O, 1 and I, so it is easy to
    read out;
  - generated by the server and checked for uniqueness;
  - used as the user's display name in study mode.
- **Stored:**
  - in `consents`: the consent version and time;
  - in the tables above: the answers, confidence and times.

  Not stored: name, email, phone, IP.
- **Withdrawal:** delete everything for that id (admin view J).
- **Retention:** until the analysis after the hackathon; then only the
  aggregate numbers are kept.
- **The free-text fields** (feedback, tutor messages) are masked as in the
  tutor, and kept for 30 days.

## The analytics module (to build after review)

| Function | Input rows | Output | Test |
|---|---|---|---|
| `item_stats(attempts, abilities)` | attempts, θ per user | the table in view B | hand-made rows with known success, gap, discrimination |
| `calibration_series(attempts, by)` | attempts | weekly confidence, score, gap, Brier | a perfectly calibrated user has gap 0 |
| `router_calibration(reco_events)` | events with `predicted_m` and `observed` | per decile and per node | a router that predicts the truth gives a diagonal |
| `tutor_overview(llm_events)` | llm events | view D | counts by check type |
| `hard_overview(attempts)` | hard attempts | view B hard panel, view F timing | the most failed test is found |
| `study_report(before, after)` | paired rows | view H | paired change on hand-made pairs |
| `next_step_candidates(router_result, unlocked, rng)` | router output | shown list with ranks and exploration flags | 10% exploration over many draws, always unlocked nodes |
| `profile_summary(user_rows, router_result)` | one user's rows | `GET /me/summary` | bands and gap from hand-made rows |
| `participant_id(existing)` | existing ids | a new unique code | no 0/O/1/I, unique |

## For review

1. Is the list of views right? What should be cut for the 48 hours? My
   proposal for Sunday:
   - A, B (easy and medium only), C, D (advice watch), G, H;
   - the rest after the demo.
2. Exploration at 10% in the next-step suggestions: acceptable for the
   demo, or off until after?
3. The auto-flag rule: 2 "wrong fact" reports turn an item back into a
   draft.
4. The consent text wording.
