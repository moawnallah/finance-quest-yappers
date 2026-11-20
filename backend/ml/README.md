# backend/ml: the tutor agent

Owner: Mateusz.

The tutor explains cards and tasks, gives hints without giving answers, and
recommends verified reading. It never gives investment advice.

**Design, contracts and the split of work:**
[docs/tutor_agent.md](../../docs/tutor_agent.md).

## What will live here

```
tutor/            answer(), context builder, router, output checks
tutor/kb_ingest.py
config/llm.yaml   roles -> models (LiteLLM), chosen by LLM_CONFIG
prompts/<role>/<version>.md
eval/             20-prompt model choice set, red-team set
tests/
```

## Rules

- Code calls roles (`router`, `tutor_small`, `tutor_cloud`), never model
  names.
- No request with user data goes to a cloud role.
- Every failure falls back to the stored explanation written by people.
