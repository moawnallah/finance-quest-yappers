# backend

FastAPI + SQLAlchemy/Alembic. SQLite by default; PostgreSQL when `DATABASE_URL` points to one. Owner: Mohamed.

Run from `backend/`: `make setup && make db && make run` (API on http://localhost:8001, docs at `/docs`). Settings: `../.env.example`.

## Endpoints

- Accounts: `POST /auth/register`, `POST /auth/login`, `GET /me`. Guests have no account: the app sends `X-Guest-Id` and `X-Guest-History`, and nothing about them is stored.
- Onboarding and path: `POST /onboarding`, `POST /path/preview`, `POST /onboarding/choose-path`, `GET /me/path`, `POST /paths/finish`, `GET /roadmap`
- Skills (engines): `GET /skills`, `GET /skills/{node}`, `GET /skills/{node}/prerequisite-test`, `GET /skills/{node}/test-out`, `GET /tasks/{id}` (easy, medium, hard), `POST /tasks/{id}/attempts`, `POST /tasks/{id}/run` (hard: public tests only)
- Tutor: `POST /tutor`, `POST /tutor/stream`
- Scales and leagues: `GET /me/scales`, `POST /me/scales`, `GET /leagues`
- Consent, feedback, study, admin views: see [docs/admin_and_profile.md](../docs/admin_and_profile.md), "API (built)"
- `GET /health`, `GET /meta`
- Older wheel endpoints, no longer used by the app: `POST /auth/session`, `POST /me/profile`, `POST /me/confidence`, `GET /wheel`, `GET /wheel/{slice}/tree`, `GET /nodes/{node_id}`, `POST /answers`, `GET /benchmark`, `POST /benchmark/answers`, `GET /me/progress`, `GET /me/badges`, `GET /leaderboard` (`GET /admin/ab-results` is still shown in the admin panel)

The backend decides node states and checks answers; correct answers never reach the browser before the user answers.

## Errors

```json
{"error": {"code": "not_found", "message": "...", "request_id": "..."}}
```
