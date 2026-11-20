# backend

FastAPI + PostgreSQL. Owner: Mohamed.

## Endpoints (draft)

- `POST /auth/session`, `POST /me/profile`
- `GET /wheel`, `GET /wheel/{slice}/tree`, `GET /nodes/{node_id}`
- `POST /answers`, `POST /tutor`, `POST /simulate`
- `GET /benchmark`, `POST /benchmark/answers`
- `GET /me/progress`, `GET /admin/ab-results`, `GET /health`

The backend decides node states (done, current, open, locked) and checks answers; correct answers never reach the browser before the user answers.

## Errors

```json
{"error": {"code": "not_found", "message": "...", "request_id": "..."}}
```
