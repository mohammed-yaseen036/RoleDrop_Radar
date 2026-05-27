# 📡 RoleDrop Radar

An enterprise-ready, low-latency, early-opportunity alert platform. RoleDrop Radar monitors official company career boards (Ashby, Greenhouse, Lever, Google Careers), standardizes job ingestion, matches listings to candidate signal profiles using a hybrid AI pipeline, and dispatches instant push notifications via Telegram and SMTP.

Designed with strict **Forward Deployed Engineer (FDE)** patterns: pluggable connector schemas, resilient rate-limiting failovers, Supabase Row-Level Security (RLS) multi-tenant isolation, and a custom diagnostics telemetry console.

---

## 🛠️ Key Architectural Strengths

* **Pluggable Source Adapter Ingestion**: Decoupled connector modules standardizing unstructured third-party job postings (leveraging Ashby, Greenhouse, Lever, and Google Board APIs) into a strict, unified `NormalizedJob` schema.
* **Hybrid Matching & Cost Mitigation**: Reserves expensive Large Language Model (Gemini 2.5 Flash Lite) tokens strictly for high-probability matching roles. A fast local regular-expression pre-filtering engine suppresses low-fit profiles and senior-level roles beforehand, **saving up to 88% in Gemini token overhead costs** ($0.04/job down to $0.0003/job).
* **Multi-Tenant Enterprise Security**: Database safety is enforced directly at the engine level through PostgreSQL **Row-Level Security (RLS)** policies scoped directly to authenticated JWT `auth.uid()`, preventing cross-tenant leakage.
* **Self-Healing Failover Pipelines**: Automated circuit breakers cleanly capture adapter connection timeouts (HTTP 504) or API rate limits (HTTP 429), gracefully logging tracebacks and falling back from cloud Gemini matching to local Ollama (`llama3:latest`) or local deterministic regexes without service interruption.
* **System Telemetry & Sandbox Console**: An administrative console displaying live health latency indicators and an interactive recruiter failover simulation panel to trigger mock outages and observe live recovery logs.

---

## 📂 System Architecture

```text
├── backend/
│   ├── app/
│   │   ├── services/
│   │   │   ├── intelligence.py   # Hybrid AI matching engine & Ollama fallbacks
│   │   │   ├── monitor.py        # Ingestion pipeline orchestrator & circuit breakers
│   │   │   ├── notifications.py  # Telegram bot & SMTP delivery dispatcher
│   │   │   └── sources.py        # Pluggable connectors (Ashby, Greenhouse, Lever, Google)
│   │   ├── main.py               # FastAPI application routing
│   │   ├── models.py             # SQLAlchemy models & schema definitions
│   │   └── cli.py                # Cron-scheduled monitor pipeline CLI
│   └── tests/                    # Robust backend integration test suite
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Dashboard with telemetry sandbox & detail drawer
│   │   ├── styles.css            # Cyber-dark custom glassmorphism design tokens
│   │   └── lib/api.ts            # Typed HTTP API Client
```

---

## ⚡ Quick Start

### Local Orchestration (Windows)
We have provided a double-clickable dev server launcher in the root directory. To spin up both the FastAPI backend and Vite React frontend concurrently in separate windows, simply execute:
```powershell
.\start-radar.bat
```

### Manual Installation

#### 1. Backend Setup
```powershell
# Copy environment configuration
Copy-Item .env.example .env

# Initialize python virtual environment
py -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt

# Run migrations & start Uvicorn
Set-Location backend
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
With `APP_ENV=development` and no Supabase variables set, the dashboard runs in local mock session mode (`X-Demo-User` authentication headers) for seamless offline testing.

#### 2. Frontend Setup
```powershell
# Copy environment configuration
Copy-Item frontend\.env.example frontend\.env

# Install dependencies and start Vite React dev server
Set-Location frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🔒 Configuration & Integrations

Configure these in the root `.env` or as deployment environment variables:

| Capability | Config Key | Description |
| --- | --- | --- |
| Hosted DB | `DATABASE_URL` | Scoped PostgreSQL connection string |
| Cloud AI Scoring | `GEMINI_API_KEY`, `GEMINI_MODEL` | Gemini models (defaults to `gemini-2.5-flash-lite`) |
| Local AI Scoring | `ENABLE_OLLAMA`, `OLLAMA_BASE_URL` | Local model fallbacks (defaults to `llama3:latest`) |
| Telegram Alerts | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` | Telegram BOT token & API secret |
| Email Alerts | `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | SMTP sender credentials |

---

## 🧪 Testing & Verification

To verify contract boundaries, execution latency, and matching rules, run the standard suite:

```powershell
# Run backend integration tests
Set-Location backend
.\.venv\Scripts\pytest

# Run frontend build verification
Set-Location ..\frontend
npm run build
```
The test suite validates multi-tenant security scopes, adapter normalization, regex pre-filters, senior-role suppression thresholds, and circuit-breaker failover logging.
