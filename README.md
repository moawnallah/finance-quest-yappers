# Finance Quest (Yappers)

Collabothon 2026, Commerzbank challenge: a gamified learning app that helps self-directed investors of every generation move from knowing to doing.

## Structure

```
frontend/          Next.js app (Michał), built from Paulina's designs
backend/           FastAPI app (Mohamed)
  data/            real market data: GPW, MSCI, NBP, GUS (Yurii)
  ml/              question generation and the tutor (Mateusz)
docs/              architecture, API notes, pitch material
.env.example       config names only, never real secrets
```

Two services run on Google Cloud Run: `frontend` and `backend`. The data and ML code live inside the backend as Python modules.

## Branches

- `dev`: push your changes here directly, with no reviews, but always add tests.
- `main`: Mohamed merges `dev` into `main` periodically once it works. Merging to `main` triggers the deployment.

## Rules

- Don't commit secrets. Put config names in `.env.example` and real values in Secret Manager.
- Add tests with every change.
