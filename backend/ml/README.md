# backend/ml: the tutor agent

Owner: Mateusz.

The tutor explains cards and tasks, gives hints without giving answers, and
recommends verified reading. It never gives investment advice.

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
prompts/tutor_small/tutor-v1.md
tests/              checks, context guard, pipeline fallbacks, ingest rules, role refusals
eval/               20-prompt model choice set, red-team set, runner
router/             onboarding router: tree.yaml, benchmarks.yaml (EB525 PL), router.py (docs/onboarding_router.md)
```

```bash
cd backend/ml
pip install -r requirements.txt
python -m pytest tests
```

Status (2026-11-20): runs with a scripted model in tests. Not yet run against a real model:
LiteLLMClient is untested until Ollama is up (OLLAMA_API_BASE, TUTOR_MODEL in .env).

## Rules

- Code calls roles (`router`, `tutor_small`, `tutor_cloud`), never model
  names.
- No request with user data goes to a cloud role.
- Every failure falls back to the stored explanation written by people.
