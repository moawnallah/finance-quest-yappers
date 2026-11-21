# Admin panel, user profile, study mode

Readers:
- Mohamed (endpoints, tables);
- Michał (screens);
- Mateusz (the analytics module and the next-step model);
- whoever runs the hallway test.

Purpose: agree what the admin panel and the profile show, where each number
comes from, and what we must log now so that a "what next" model can be
trained later.

Status: decisions taken 2026-11-21 (end of file). Built on branch
`admin-panel` (section "API (built)"). Screens are not built yet. The
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
| `reco_events` | from the router (docs/tutor_agent.md, section 6) | Router overview and calibration |
| `node_opened` (in `events`) | `node, source (recommended / self_chosen / explore_wheel / tutor_link)` | Self-chosen clicks for the next-step model |
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
- **Red alert (decided 2026-11-21).** An item with 2 or more open "wrong
  fact" reports raises a red alert on the overview and is highlighted in
  view B. It stays live; a person decides.

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

**The end-of-path screen is the decision point.**
- It congratulates the user and recommends 3 next nodes, for example
  "You finished your path. To grow further we recommend: x, y, z", each
  with a one-line reason.
- It always offers "Something else" (opens the tree and the Explore
  wheel).
- Optionally it asks a 30-second check-in of 3 short questions:
  - "Has your goal changed?" (same answer set as the survey);
  - "How sure do you feel about money decisions now?" (1-5);
  - "What would you like next?" (protect / grow / understand the
    markets / not sure).

  The answers update the needs, and the confidence answer gives a
  before/after pair for the study view.

**Signals we collect for the next step:**

| Signal | Source | Why it matters |
|---|---|---|
| Scores and initial answers | the survey, every first attempt, the mastery per node | What the user can do now |
| The check-in | the end-of-path screen | What the user wants now, and confidence after the path |
| **Self-chosen clicks** | every node, card or Explore slice the user opens **without** it being recommended (`node_opened` with `source: recommended / self_chosen / explore_wheel / tutor_link`) | What interests the user, beyond our suggestions |
| The pick on the end-of-path screen | one of x, y, z, "something else", or leaving | The label for the next-step model |
| The outcome of that pick | first-item success, node completed, back within 7 days | Whether the pick was a good one |

**Why the self-chosen clicks matter.** If we log only picks from our own 3
suggestions, a model can only learn our rules back. Nodes users open on
their own are the alternatives the rules did not offer. They show what a
better recommender could have suggested, without us changing anything for
the user.
- Optional later, not for the demo: occasionally show one random unlocked
  node among the 3 suggestions. That would add alternatives faster, but
  self-chosen clicks are enough to start.

**One row per decision point** (`next_step_events`):

| Field | Content |
|---|---|
| `ts, user_pseudo_id, decider, decider_version` | when, who (pseudonymous), which model made the suggestion (`rules-1` today) |
| `trigger` | `path_finished` or `node_finished` |
| `state` | mastery per node, calibration gap, needs, goal, horizon, age band, days since start, recent scores, check-in answers, self-chosen clicks in the last 7 days |
| `candidates` | the 3 suggested nodes with rank, priority and reason; also the shadow model's suggestions, if one runs |
| `chosen` | x, y, z, a node picked through "something else", or none |
| `outcome` | filled later: first-item success in the chosen node, node completed (yes or no), back within 7 days, confidence change |

Every `node_opened` event (with its `source`) is also kept, so self-chosen
learning outside a decision point is not lost.

**A decision model in shadow at the end of the path** (documentation only;
the demo has only two prepared paths):
- BASAL (a `choice` question over the unlocked nodes, plus the state as
  JSON) or Gemma (the same prompt with a JSON answer) proposes x, y, z
  next to the rules.
- The rules decide; the shadow proposal is logged in `candidates`.
- This is the same set-up as the onboarding shadow experiment
  (onboarding_router.md).

**Admin view:**
- dataset size and the share of rows with an outcome;
- the share of picks that were self-chosen;
- agreement between the rules and the shadow model;
- class balance;
- an anonymised CSV export.

### Replacing a model with our own (router and next step)

The same logs serve the **onboarding router now** (calibration: predicted
vs observed first items) and **a replacement later**.
- The rules stay until a model beats them on held-out users.
- The decider's name and version are on every logged row, so results can
  be compared by version.

| Step | What | Pass criterion |
|---|---|---|
| 1. Collect | `reco_events`, `next_step_events`, `node_opened`, attempts | a few hundred decision points with outcomes; first items per node for the router |
| 2. Candidates | (a) **our own classifier**: logistic regression or gradient boosting predicting "first-item success and completion" per candidate node; (b) **segments**: k-means on the state (mastery, calibration, goal, horizon), then per segment the nodes with the best outcomes; (c) the shadow decision model (BASAL or Gemma) | — |
| 3. Offline comparison | the same held-out users; the router's metric is log loss and Brier of predicted first-item success; the next-step metric is the outcome rate of the suggested nodes, measured where the user's pick matched the suggestion | better than the rules by an agreed margin, decided before looking |
| 4. Shadow | the candidate runs next to the rules, logged only | it agrees where the rules are good, and disagrees where outcomes say the rules were wrong |
| 5. Switch | A/B on a share of new users (Mo's variants), with a new `decider_version` | the outcome rate does not drop; the advice and leak checks stay clean |

k-means alone does not predict anything. It groups similar users. It earns
its place only if per-segment suggestions beat the rules in step 3.

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

## Demo mode and the end of a path (built 2026-11-21)

1. **Survey.** The survey stays for everyone, because the client profile
   is valuable for stakeholders. There is no public skip button; the
   presenter fills it in quickly for a persona.
2. **Path.** See onboarding_router.md, "Demo mode": the recommended path,
   or "not ready yet, choose one of the two" (`POST
   /onboarding/choose-path`).
3. **End-of-path check-in,** about 30 seconds (`POST /paths/finish`):
   - "Do you think you made progress?" (yes / somewhat / no);
   - confidence 1-5 in each area of the path;
   - "What is your next goal?"
4. **Thanks screen:** "Thank you for finishing the path. This is a demo,
   and we are very happy you tested it: we hope you learned something you
   can use. If you like, try the other path too."
   - **Optional feedback:** one tap to rate, a comment if the user likes
     (`POST /feedback` with `where: mission`, `kind: rating`). It is
     optional because forced feedback gives poor answers; the check-in
     already collects the structured data.
   - **The other demo path** is offered.

All of it is stored: the check-in in `path_checkins`; `path_chosen`,
`path_finished` and `demo_match` in `reco_events`.

## Client insights (aggregate, for stakeholders)

`GET /admin/client-insights` gives an overview of our users that a bank
could use to see which tools and education its customers need:
- **profile:** age band, goal, horizon, buffer, products held;
- **knowledge:** knowledge bands, and the share rating themselves high but
  scoring 0-2;
- **learning needs:**
  - no buffer or under a month;
  - consumer loan;
  - wants to invest but holds nothing;
  - crypto;
  - retirement goal without a pension product;
- **topics:** the most needed topics;
- **paths:** ready vs not ready, and which demo path was chosen;
- **after the path:** progress, next goal, confidence by area.

**Privacy rules, built in:**
- aggregates only; nothing is listed per person;
- any group smaller than 5 people is hidden, and the threshold cannot be
  set lower than 5;
- the current consent text says "student project". Sharing data with a
  bank, even aggregates under a bank's name, would need a consent text
  that says so. Sharing individual profiles would need explicit consent
  and a legal basis (GDPR profiling rules). Check with the Commerzbank
  mentor before any pitch claim beyond "aggregate insights".

## API (built 2026-11-21, branch `admin-panel`)

Routes are in `backend/app/insights_api.py`; the numbers come from
`backend/ml/analytics`. Admin routes need the `X-Admin-Key` header.

| Route | For | Returns |
|---|---|---|
| `POST /onboarding` | survey screen | knowledge score, band, benchmarks, path, challenges, goal; stores the survey, the result and `reco_events` |
| `GET /me/summary` | profile | path, goal, challenges, benchmarks, panels with node bands and done flags, calibration (gap, words, Brier, weekly, badge), hard results, activity |
| `POST /events/node-opened` | every node open | logs `node` and `source` (`recommended`, `self_chosen`, `explore_wheel`, `tutor_link`, `end_of_path`) |
| `POST /feedback` | "Report a problem", mission rating | stores the report; the text is masked |
| `GET /study/consent`, `POST /study/join` | hallway test | consent text and version; a session under a random participant id (no name). `join` needs the facilitator's `X-Study-Key` (`STUDY_KEY`) or the admin key |
| `POST /onboarding/choose-path` | "not ready yet" screen, "try the other path" | stores the pick, logs `path_chosen` |
| `POST /paths/finish` | end of a path | stores the check-in; returns the thanks message, the optional feedback ask, the other path |
| `GET /admin/client-insights` | stakeholders | aggregate client overview, groups under 5 hidden |
| `GET /admin/overview` | view A | tiles and alerts (reports red, item flags amber, advice red) |
| `GET /admin/items` | view B | item and task quality from first attempts; the hard panel (acceptance, most failed test, points histogram, growth, `duration_ms` p50/p95) |
| `GET /admin/calibration` | view C | weekly confidence vs score overall and by age band; onboarding self-rating vs knowledge score |
| `GET /admin/advice-watch` | view D | tutor overview with the advice alert (empty until the tutor writes `llm_events`) |
| `GET /admin/reco-events` | view E | the latest router events |
| `GET /admin/node-opened` | view I | clicks by source and the self-chosen share |
| `GET /admin/feedback`, `PATCH /admin/feedback/{id}` | view G | reports with red alerts; status changes are logged |
| `GET /admin/study`, `DELETE /admin/study/{participant_id}` | view H | paired before/after results; withdrawal deletes everything for that code |

**Hard tasks in the task API:**
- `GET /tasks/{id}` and `GET /skills/{node}` serve hard tasks, including
  `question.blockly`.
- `POST /tasks/{id}/attempts` accepts a Blockly workspace or a program.
  It returns `accepted`, `points` and `growth_index`, with the test
  results and story in `reveal.result`.
- The attempt stores `points`, `growth_index`, `failed_test` and
  `duration_ms`.

**The challenge rule** is in `node_status`: a passed test-out completes the
whole node.

**Migration:** `7c1e5a9d2b40` adds the tables and the attempt fields. On
Vercel the tables are created at start-up, as before.

**Tests:** 8 in `backend/tests/test_insights.py` and 9 in
`backend/ml/tests/test_analytics.py`.

**Not built yet:**
- the screens;
- `POST /tutor` and its `llm_events` writer;
- the end-of-path screen's `GET /me/next-steps`;
- the first-attempt rule for completion in `node_status` (Mo's fix 2; the
  admin metrics already use first attempts).

## The analytics module (built 2026-11-21)

| Function | Input rows | Output | Test |
|---|---|---|---|
| `item_stats(attempts, abilities)` | attempts, θ per user | the table in view B | hand-made rows with known success, gap, discrimination |
| `calibration_series(attempts, by)` | attempts | weekly confidence, score, gap, Brier | a perfectly calibrated user has gap 0 |
| `router_calibration(reco_events)` | events with `predicted_m` and `observed` | per decile and per node | a router that predicts the truth gives a diagonal |
| `tutor_overview(llm_events)` | llm events | view D | counts by check type |
| `hard_overview(attempts)` | hard attempts | view B hard panel, view F timing | the most failed test is found |
| `study_report(before, after)` | paired rows | view H | paired change on hand-made pairs |
| `next_steps(state, unlocked)` | mastery, needs, check-in answers, self-chosen clicks | the 3 end-of-path suggestions (x, y, z) with reasons, from the rules; only unlocked, not-done nodes | hand-made states give the expected 3; a self-chosen topic raises its related nodes |
| `click_signals(node_opened)` | `node_opened` events | self-chosen share, top self-chosen nodes per user and overall | recommended clicks are not counted as self-chosen |
| `profile_summary(user_rows, router_result)` | one user's rows | `GET /me/summary` | bands and gap from hand-made rows |
| `participant_id(existing)` | existing ids | a new unique code | no 0/O/1/I, unique |

## Decisions (2026-11-21)

1. **For Sunday:** views A, B (easy and medium), C, D (advice watch), G and
   H. The rest comes after the demo.
2. **No random suggestions.** Self-chosen clicks, scores, initial answers
   and an optional end-of-path check-in are the signals. The end-of-path
   screen congratulates the user and recommends x, y, z. A shadow decision
   model (BASAL or Gemma) at the end of the path is documented, not built
   for the demo. The logs serve the router now and a replacement later
   (own classifier or k-means segments, only if it beats the rules).
3. **Reports:** a red alert at 2 "wrong fact" reports; the item stays live.
4. **The consent text** is accepted for now.

The code status of each piece is in "The analytics module".

## Export (data contract)

`GET /admin/export?table=<table>&format=csv` (admin key or admin account). One CSV per table for the
bank's data platform.

**Rules**
- Pseudonymous ids only: `user` is the first 10 characters of sha256(user id), the same id the admin
  panel shows.
- Row-level tables contain only learners who turned on "Share my learning profile with the bank".
- No free text: no prompts, answers, feedback text or names.
- Synthetic demo learners are left out unless `synthetic=1` is passed.

**Tables**

| Table | Column | Type | Meaning |
|---|---|---|---|
| attempts | user | text | Pseudonymous learner id |
| | task_id, node_id | text | The question or task and its skill-tree node |
| | level | text | easy, medium or hard |
| | context | text | practice, prerequisite or test_out |
| | score | number 0-1 | The engine's score (empty for reflections) |
| | confidence | integer 1-5 | "How sure are you?" |
| | points | integer | Hard tasks: 51-100 when accepted |
| | duration_ms | integer | Engine time to score |
| | submitted_at | ISO 8601 | When the answer was sent |
| reco_events | user, ts, event_type | text | Router and recommender events (path issued, demo_match, path_chosen, path_finished, next_steps_shown, shadow_decision) |
| | router_version, node | text | Router version and node |
| | predicted_m, need, priority | number | The router's mastery estimate, need and priority |
| | path | JSON list | Node ids of a path |
| llm_events | user, ts, mode, intent, model | text | One tutor call (model "cache" for a cache hit) |
| | latency_ms, tokens_in, tokens_out | integer | Cost of the call |
| | fallback_used, flagged_for_review | boolean | Whether the stored text was shown, and the review flag |
| | checks_failed | JSON list | Names of failed output checks |
| surveys | user, created_at | text | The starting survey |
| | age_band, goal, horizon, self_rating, experience | text | Survey answers |
| | knowledge_score, band | integer / text | Quick-check result (empty when skipped) |
