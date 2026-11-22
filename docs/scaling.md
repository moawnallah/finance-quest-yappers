# Scaling and caching

Readers:
- Mo: runs the backend, the database and the GPU box;
- the pitch owner: what we can say about load, and what is measured.

Purpose: where the load is, which caches to add, what to show in the
admin panel, and the load test that gives the numbers.

Status (2026-11-22): layers 1 and 2 of the tutor cache and the admin
metrics are built (Mohamed, 2026-11-21). Layer 3 and the load test are
not. No load test has run yet; the only measurements are Mohamed's local
latency runs (docs/tutor_agent.md, section 3; docs/onboarding_router.md,
"Built"). The "Now" lines are read from the code on
main.

## Where the load is

| Part | Now | Cost per request |
|---|---|---|
| API | FastAPI with uvicorn (2 workers) on one Oracle VPS behind Caddy and Cloudflare Tunnel, SQLite (`app/db.py` also supports Postgres: pool 2 + overflow 3, pre-ping, recycle 300 s) | Small: reads, pure-Python scoring |
| Content | Catalog and card passages loaded once per instance (`lru_cache`) | One load per cold start |
| Hard tasks | `POST /tasks/{id}/attempts` runs the plan on every hidden event and 200 futures | CPU per submit; to measure |
| Tutor | Gemma in Ollama on one GPU (`OLLAMA_API_BASE`), `keep_alive` 30 min, `think` off, temperature 0.3 | The expensive part: seconds per answer |
| Router | Pure Python; with `BASAL_MODE=primary`, one BASAL call of up to 3 s inside `POST /onboarding`, cached per survey in the process | Small, except the BASAL call on a cache miss |

So scaling means scaling the tutor first. The rest needs connection pooling
and cold-start care.

## Caching the tutor

Three layers, from free to most work.

**1. Prompt prefix (KV) cache in Ollama.**
- Ollama keeps the model loaded for `keep_alive` and can reuse the work on
  a prompt prefix that repeats from the previous request in the same slot.
  This works only if the start of the prompt is byte-identical.
- Rule: the fixed system prompt comes first; everything per request
  (context, history, the learner's message) comes after it. Both
  `tutor_api.build_messages` and our pipeline already put the system
  prompt first.
- What breaks it: anything that varies inside the first system message.
  The Mermaid skill appended for `visual` gives a second prefix, which is
  fine. A timestamp or a user name there would break every request.
- Measure it: Ollama's reply has `load_duration`, `prompt_eval_count`,
  `prompt_eval_duration`, `eval_count` and `eval_duration`. Since
  2026-11-21 `llm_events` also stores them as `load_ms`, `prompt_eval_ms`
  and `eval_ms`. A falling
  `prompt_eval_duration` on repeated prefixes shows the cache working; a
  large `load_duration` shows a cold model load.

**2. Answer cache for requests that are the same for everyone.** Built
2026-11-21 as below (`app/tutor_api.py`: `cache_key`, `cache_get`,
`cache_put`; table `tutor_cache`, migration `d3f7a1c9e284`). The key uses
`PROMPT_VERSION` for pipeline modes and `MO_PROMPT_VERSION` otherwise. In
production it never hit at first, because chat questions carry no node;
since 2026-11-22 a first chat question without history is cached too,
under the node "-".
- Cache only requests without anything personal or attempt-specific:
  - `explain_concept` with a node, no history, no task attempt;
  - after masking (`tutor.rules.mask`) the message is unchanged, so it
    held no personal data.
- Never cache:
  - `hint` and `explain_result`: they depend on the learner's attempt and
    draft;
  - anything with history;
  - fallbacks: a failed answer should be tried again.
- Key: hash of (prompt version, model, mode, node, normalized message:
  lower case, collapsed spaces).
- Value: the answer text and its Mermaid diagram.
- TTL: a day.
- Changing the prompt version or the model changes the key. Editing a
  card does not: after a content fix, clear the cache
  (`DELETE /admin/tutor-cache`).
- Store: the `tutor_cache` table in the app database (SQLite in
  production), shared by both worker processes. This was planned for
  serverless instances, which share no memory; it fits the VPS too.
- Effect on the learner: the same question gets the same answer. At
  temperature 0.3 the answers vary only a little anyway.
- Log a hit as an `llm_events` row with `model` "cache" and its latency.
  The admin views then count hits without a new table.

**3. HTTP caching for content.** `GET /roadmap` is the same for everyone:
`Cache-Control: public, max-age=300`. Per-user routes stay `no-store`.

## Admin panel: what to show

From `llm_events`, per mode and per day:
- requests;
- p50 and p95 latency;
- tokens in and out;
- fallback rate and the failed checks;
- cache hit rate (layer 2);
- cold loads (`load_duration` over 1 s, once logged);
- `prompt_eval_duration` p50 (layer 1).

Also a "clear tutor cache" button (admin key), for after a content fix.

Built 2026-11-21 as `GET /admin/tutor-metrics` (per mode, over all rows:
requests, p50 and p95, fallback rate, cache hit rate, cold loads,
prompt-eval p50, and the number of cached answers) and `DELETE
/admin/tutor-cache`. Not built yet: the split per day, tokens, and failed
checks.

## Scaling the model

- **One GPU.**
  - `OLLAMA_NUM_PARALLEL` sets how many requests run at once. Each slot
    needs its own context memory, so more slots means less context per
    slot or a smaller model.
  - `OLLAMA_MAX_QUEUE` caps the queue. A refused or timed-out call already
    ends in our fallback, the stored explanation. The learner gets a
    correct, plainer answer, and the admin panel shows the fallback.
- **More users.** A second GPU box behind a load balancer, or vLLM, which
  batches requests and caches prefixes automatically. Decide this from the
  load test, not before.
- **The BASAL call.** In primary mode it sits inside onboarding: up to
  3 s on a cache miss. The cache lives in one process, so several
  processes or instances each ask BASAL again. At scale: keep its answers
  in a table (like `tutor_cache`), or show the router's path at once and
  let BASAL's path replace it from a background job. In shadow mode the
  call is logged only and can move to a queue.

## Database

- **Connections.** Use the provider's pooled connection string (PgBouncer
  or similar). Each serverless instance holds up to 5 connections
  (`pool_size` 2 + `max_overflow` 3), so 20 warm instances can hold 100.
- **Migrations.** Run them as a deploy step (`alembic upgrade head`).
  `create_all` runs only for the SQLite demo database.

## Load test (to run in the test environment)

**Hypothesis.** The tutor's p95 latency stays under 10 s, with under 5%
fallbacks, up to N concurrent learners on one GPU. N is what we measure.

**Script.** k6 or Locust; each virtual user:
1. starts a session;
2. sends the survey;
3. answers 5 items;
4. asks the tutor 3 times: `explain_concept` twice (one repeated, to see
   the cache) and one `hint`.

**Steps.** 5, 10, 20 and 50 concurrent users, 5 minutes each.

**Record:** p50 and p95 per route, tutor fallback rate, cache hit rate, GPU
memory, and Postgres connections.

**Interpretation.**
- N is the last step that meets the hypothesis.
- If the hint p95 fails first, the GPU is the limit: tune
  `OLLAMA_NUM_PARALLEL`, or add a box.
- If API routes without the tutor slow down, the database or cold starts
  are the limit.

**For the pitch.** Only the measured N, with the hardware named. Until the
test runs: "designed to degrade to stored explanations under load".
