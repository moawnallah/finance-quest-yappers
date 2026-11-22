# backend/ml: the tutor agent

Owner: Mateusz.

The tutor explains cards and tasks, gives hints without giving answers, and
recommends verified reading. It is designed not to give investment advice (docs/responsible_ai.md).

**Design, contracts and the split of work:**
[docs/tutor_agent.md](../../docs/tutor_agent.md).

## Layout

```
tutor/models.py     TutorRequest, TutorResponse, LLMClient and ContextProvider interfaces
tutor/pipeline.py   answer(): kill switch, masking, rule intents, context, one model call, checks, fallback
tutor/context.py    context by mode (no truth before submission)
tutor/checks.py     the five output checks
tutor/rules.py      personal-data masking, advice and injection rules, safe templates
tutor/kb.py         ingest reviewed cards from backend/content, SEARCH_SQL for Postgres, in-memory search
tutor/llm.py        LiteLLMClient: roles -> models from config/llm.yaml, refusals before any call
config/llm.yaml     roles -> models, ${ENV} values
prompts/tutor_small/tutor-v2.md
tests/              checks, context guard, pipeline fallbacks, ingest rules, role refusals
eval/               20-prompt model choice set, red-team set, runner; api_run.py runs them through /tutor
router/             onboarding router: tree.yaml, benchmarks.yaml (EB525 PL), router.py, shadow.py (BASAL client)
                    (docs/onboarding_router.md)
experiments/        basal_shadow/run.py: BASAL against the router on the test personas
```

```bash
cd backend/ml
pip install -r requirements.txt
python -m pytest tests
```

Status (2026-11-22): on the server the pipeline calls Ollama through `app/tutor_api.call_model`
when `TUTOR_PIPELINE=true` (docs/tutor_agent.md, section 5). LiteLLMClient is used only by the
offline eval runner. The red-team run on the real model through `eval/api_run.py` and its
results are in docs/tutor_agent.md, section 3. Production runs with the pipeline off.

## Rules

- Code calls roles (`router`, `tutor_small`, `tutor_cloud`), never model
  names.
- No request with user data goes to a cloud role.
- Every failure falls back to the stored explanation (the card's text; prototype content was
  drafted with AI and awaits expert review, docs/content_authoring.md).
