# Finance Quest (Yappers)

Collabothon 2026, Commerzbank challenge: a gamified learning app that helps self-directed investors of every generation move from knowing to doing.

## Structure

```
frontend/          Flutter app (Michał), built from Paulina's designs
backend/           FastAPI app (Mohamed)
  data/            real market data: GPW, MSCI, NBP, GUS (Yurii)
  ml/              question generation and the tutor (Mateusz)
docs/              architecture, API notes, pitch material
.env.example       config names only, never real secrets
```

Two services run on Google Cloud Run: `frontend` and `backend`. The data and ML code live inside the backend as Python modules.

## Branch

- `main` is the only branch. Push small, working changes and always add tests.
- Every push to `main` deploys, so pull before you push and keep `main` working.

## Rules

- Don't commit secrets. Put config names in `.env.example` and real values in Secret Manager.
- Add tests with every change.
