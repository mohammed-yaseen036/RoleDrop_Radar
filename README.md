# RoleDrop Radar

RoleDrop Radar is an early-opportunity alert platform: candidates upload a resume, select official company career sources, and receive Telegram/email notifications when a newly published role is a strong profile match.

It is built around one careful claim: applying while a suitable role is fresh can reduce time-to-application. It does not claim that being early guarantees an ATS pass, assessment or interview.

## What Is Built

- React + TypeScript dashboard for sign-in, resume onboarding, monitored sources, opportunities and alert logs.
- FastAPI service with Supabase-compatible authentication, tenant-scoped records and SQLite development mode.
- Resume PDF extraction followed by deletion of the uploaded file; only editable structured profile data is persisted.
- Official-source adapters for Ashby, Greenhouse and Lever, plus a best-effort Google Careers adapter that fails cleanly if public access changes.
- Deterministic prefiltering plus optional Gemini structured scoring through `gemini-2.5-flash-lite`.
- Cost-safe initialization: historical roles are imported and scored deterministically on first sync; Gemini is reserved for newly observed or updated candidate-fit roles.
- Optional local Ollama extraction fallback using `llama3:latest`; cloud monitoring falls back to deterministic scoring because it cannot access a laptop-local model.
- Telegram linking, SMTP email notifications and delivery history.
- Scheduled monitor CLI and GitHub Actions workflow configured for five-minute polling.
- Alembic schema migration, Supabase RLS policy file and Render deployment blueprint.
- Tests and a 30-role labeled evaluation dataset.

LinkedIn is intentionally not scraped or automated. Users can monitor supported official public boards and apply through the original official link.

## Local Run

### Backend

```powershell
Copy-Item .env.example .env
py -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
Set-Location backend
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

With `APP_ENV=development` and no Supabase values, the dashboard uses explicit demo-user headers so the full workflow can be demonstrated locally.

### Frontend

```powershell
Copy-Item frontend\.env.example frontend\.env
Set-Location frontend
npm install
npm run dev
```

Open `http://localhost:5173`, enter an email in local demo access, upload a PDF resume, confirm the profile, select a source and run the first local scan. Existing roles are imported silently; later newly detected high-fit roles create alert records.

## Live Integrations

Set these in the root `.env` for backend development or as deployment secrets:

| Capability | Values |
| --- | --- |
| Multi-user authentication | `SUPABASE_URL`, `SUPABASE_ANON_KEY`; also set matching `VITE_` values for the frontend |
| Hosted database | `DATABASE_URL` from Supabase Postgres |
| AI scoring | `GEMINI_API_KEY`, optional `GEMINI_MODEL` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET` |
| Email | `SMTP_USERNAME`, `SMTP_PASSWORD` (Gmail app password), `SMTP_FROM` |

For Telegram, expose `POST /webhooks/telegram` and register that endpoint with Telegram using the same webhook secret. Each user then clicks **Connect Telegram bot** in the dashboard and starts the bot using their one-time link.

The v1 email path sends notifications from one configured SMTP sender account to each authenticated user email; it does not read anyone's inbox.

## Deployment Shape

1. Create a Supabase project, apply the Alembic migration through the backend connection, then apply [the RLS policy file](./supabase/migrations/202605250002_row_level_security.sql).
2. Deploy `render.yaml` for the static dashboard and FastAPI API; configure all values marked `sync: false`.
3. Add repository secrets required by [.github/workflows/monitor.yml](./.github/workflows/monitor.yml), especially the same `DATABASE_URL`, Gemini key and notification credentials.
4. Enable GitHub Actions. Scheduled workflows are approximate under free infrastructure; the product promise is alerts in about 5-10 minutes, not guaranteed immediate delivery.

The API must connect using a trusted server-side database credential. Browser access relies on Supabase authentication and RLS; the FastAPI endpoints independently filter all user-owned records by authenticated user ID.

## Verification

```powershell
Set-Location backend
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m app.evaluate

Set-Location ..\frontend
npm run build
```

Coverage includes PDF deletion, profile confirmation, source recognition, LinkedIn-source rejection, adapter normalization, tenant isolation, senior-role suppression, silent first sync and subsequent high-fit alert delivery logging.

## Key API Routes

| Route | Purpose |
| --- | --- |
| `POST /api/profile/resume` | Extract structured profile from PDF and delete temporary file |
| `PUT /api/profile` | Edit and confirm monitoring profile |
| `GET /api/sources/catalog` | View preset official sources |
| `POST /api/subscriptions` | Monitor a preset or supported official board URL |
| `PATCH /api/subscriptions/{id}` | Toggle monitoring or notify-all alerts |
| `GET /api/jobs` | Fetch ranked opportunities for the authenticated user |
| `GET /api/alerts` | Fetch delivery history |
| `POST /api/integrations/telegram/link` | Create one-time Telegram linking URL |
| `POST /webhooks/telegram` | Finish Telegram chat linking |
| `POST /api/monitor/run` | Development/manual monitor trigger |

## Project Boundary

V1 monitors only official sources with a documented or publicly consumable job-posting surface. It does not auto-apply, store LinkedIn credentials, evade bot protection, or imply that match scores predict hiring outcomes.
