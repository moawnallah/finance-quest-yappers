# Limitations and next steps

Readers: the jury, a bank considering a pilot, and the team.

Purpose: what the prototype does not do yet, and what we would build next,
scaling included. Details are in the linked docs.

Status: 2026-11-22, read from the code on main.

## Limitations

**Content** ([content_authoring.md](content_authoring.md))
- 11 of the 32 missions on the tree have content; the rest are visible but
  locked.
- The content was drafted by AI. Only the two hard tasks have a named
  reviewer; the 11 node files and the two Day-X tasks have none, and are
  served because `SERVE_DRAFTS` is on.
- Two Day-X tasks and two hard tasks in all.
- Three real data series. Commercial-use terms for GUS and NBP, and the
  third-party status of the OECD index, still need a person to check.

**Path choice** ([onboarding_router.md](onboarding_router.md))
- The router's parameters come from published Eurobarometer tables and are
  not tuned on outcomes.
- BASAL chooses paths in production, behind a router fallback. Whether its
  choices beat the router's is not measured: that needs first-question
  outcomes and an A/B test, which is designed and not yet built
  ([responsible_ai.md](responsible_ai.md), "Monitoring BASAL").
- BASAL is not fully stable: in Mohamed's persona run some decisions
  flipped when only something irrelevant changed, and a fifth of its
  answers were below the confidence threshold (numbers in
  [onboarding_router.md](onboarding_router.md), "Built"). The guards and
  the fallback limit the effect on the path.
- When BASAL selects no candidate (no `start_p` of 0.5 or more), the path
  is the router's first step topped up from the router's path, and the
  row still says `decided_by: basal`. Shares of BASAL decisions need this
  case counted separately until the log is fixed.
- 89% of the inputs the app sends got a path whose missions are not all
  written yet (measured on the router on 2026-11-21, before BASAL decided);
  those learners pick one of the two demo paths.
- BASAL's answers are cached per worker process.

**Tutor** ([tutor_agent.md](tutor_agent.md))
- Production runs the original tutor path (`TUTOR_PIPELINE` off). There the
  tutor is guarded by its instructions, masking and one advice pattern on
  its replies; the output checks run only in the pipeline.
- The pipeline passed its red-team run on the real model, on a local API
  (results in [tutor_agent.md](tutor_agent.md), section 3). It has not
  been switched on in production: decided 2026-11-22 to keep the original
  tutor for the demo, because the pipeline was tested only locally,
  answers without word-by-word streaming, and fell back to the stored
  explanation too often on ordinary questions.
- Limits (since 2026-11-22): 8 messages a minute and 80 a day per account;
  guests are counted per IP address, so a room sharing one network shares
  one guest limit. The minute counter and the guests' daily counter live
  in each of the two worker processes, so the effective limit can be up
  to twice as high. Chat titles and diagram repairs skip the limiter, but
  an account's daily count includes logged diagram repairs.
- In production the advice pattern is checked once the reply is
  complete; a streamed reply can show briefly before it is replaced.
- `TUTOR_ENABLED=false` stops model calls, but answers already cached are
  still served.
- Gemma runs on a single machine.

**Day-X data**
- The charts use final figures, which can differ from what was published
  on the task date; in I2 the difference is 0.2 points of inflation
  ([content_authoring.md](content_authoring.md), "Real data").

**Hard tasks** ([hard_engine.md](hard_engine.md))
- The block workspace is hard to use on a phone; the app recommends a large
  screen.

**Privacy** ([responsible_ai.md](responsible_ai.md), "Client privacy")
- No retention job, and no access or deletion on request beyond study
  participants.
- No data protection impact assessment yet.

**Evidence**
- No study with learners yet: the hallway test is planned, and is not a
  controlled trial.
- No load test: we have no measured number of concurrent users
  ([scaling.md](scaling.md)).

**Operations**
- One Oracle VPS behind Caddy and Cloudflare Tunnel, uvicorn with 2
  workers, SQLite. The database and the model each run on a single
  machine.

## Next steps

**Evidence first**
1. Hallway test on one mission: items and confidence before and after,
   reported with n.
2. A/B test of BASAL against the router on first-question outcomes, with the
   metric and sample size fixed in advance.
3. The load test.

**Content**
- An expert reviews every existing file; then `SERVE_DRAFTS=0`.
- Missions for the bank's own product types and customer groups, written
  through the process in [content_authoring.md](content_authoring.md).
- Day-X tasks with a scenario set before the reveal.
- A Polish version (BASAL already handles Polish; Bielik for the tutor).

**Product**
- A personalised version linked to the bank account, with consent
  ([responsible_ai.md](responsible_ai.md)).
- The sandbox as a work-sample test for hiring, if a firm wants it, after a
  legal review ([content_authoring.md](content_authoring.md), "Hard tasks").

**Tutor**
- Move production to the checked pipeline (`TUTOR_PIPELINE=true`). First
  test it in a test environment on the demo script (both paths, as a guest
  and from an account, a diagram request, an advice question, a hint after
  a Day-X answer), and lower the fallback rate on ordinary questions.
- Keep the rate-limit counters in a shared store, so they hold across
  workers.

**Found and fixed before the deadline (2026-11-22)**

| Finding | Fix (Mohamed, deployed 2026-11-22) |
|---|---|
| Without `TUTOR_PIPELINE`, the learner's message reached the model unmasked | Masked before every model call (commit a862c2d) |
| No per-user rate limit or daily budget on the tutor | 8 a minute and 80 a day per account or guest IP (a862c2d) |
| Flagged tutor answers could not be labelled | Labelling in the admin panel, `review_label` column (1804970) |
| The tutor cache never hit in production: chat questions carry no node | First chat questions without history are cached too (a862c2d) |
| Action blocks had fixed arguments (`cash`, the first asset), so neither hard task could be solved in Blocks mode | An amount gap and an asset chip on the actions that take them; both reference programs built from blocks in a widget test (6fc8399) |
| Diagram repairs counted toward the tutor limit | They skip the limiter like chat titles; an account's daily count still includes them (b628fcd) |

**Scaling** ([scaling.md](scaling.md))
- **The tutor is the bottleneck.** Tune Ollama's parallel slots on the GPU
  we have; then add a second GPU box, or move to vLLM, which batches
  requests and reuses prompt prefixes. Choose by the load test.
- **Tutor answers** that are the same for everyone (a mission's concept
  question, or a first chat question) are already cached for a day; the
  cache hit rate in the admin panel shows how much this saves.
- **BASAL.** Keep its answers in a shared table instead of one process, or
  compute the path in a background job and show the router's path first.
- **Database.** Postgres with a pooled connection string, and migrations as
  a deploy step.
- **Content.** Expert review is the limit: the number of reviewers sets how
  fast missions can be added.
- **Content routes.** HTTP caching for responses that are the same for
  everyone (`GET /roadmap`).
