# RoleDrop Radar: Forward Deployed Engineer (FDE) Architecture Brief

Welcome to the architectural design brief for **RoleDrop Radar**. This project is engineered specifically to showcase patterns, paradigms, and resilience designs valued by elite technical teams (like Palantir, Scale AI, OpenAI, and Retool) hiring **Forward Deployed Engineers (FDEs)**.

As an FDE, my focus is not just on writing software, but on **safely deploying, integrating, and scaling platform capabilities inside complex, high-stakes client environments**. This document details the enterprise-grade integration patterns built directly into this platform.

---

## 🏗️ 1. Pluggable Connector & Adapter Pattern
In enterprise settings, data sits across various siloed third-party APIs and proprietary portals. RoleDrop Radar utilizes a strict **Pluggable Adapter Pattern** to standardize data ingestion.

* **Standardized Normalization**: Regardless of whether the source board is Greenhouse, Lever, Ashby, or Google Careers, all entries are transformed into a strict `NormalizedJob` Pydantic model (`backend/app/services/sources.py`).
* **Clean Failover Separation**: Adapters do not directly call DB writers. They fetch, parse, and yield clean schemas. If an adapter fails (e.g. Google's page structure changes), the orchestrator captures the failure cleanly, logs the diagnostic error in `Failed Sources` telemetry, and continues parsing the remaining boards without disrupting core service pipelines.

---

## ⚡ 2. Cost-Safe Hybrid Match & Ingestion Pipeline
Naively passing every single parsed job posting to a Large Language Model (like Gemini) is financially prohibitive and represents a severe architectural flaw. FDEs design for **resource efficiency**.

RoleDrop Radar implements a **Hybrid Matching Pipeline** to mitigate SaaS API costs:

1. **Deterministic Caching Filter (Stage 1)**:
   - On initial board sync (e.g., watching a new Ashby board), all historical jobs are imported **silently** without LLM scoring, seeding the DB.
   - An extremely fast, local regular-expression matching engine (`deterministic_match` in `backend/app/services/intelligence.py`) scores skills, roles, and locations.
2. **Conditional Gemini Activation (Stage 2)**:
   - Gemini API (`gemini-2.5-flash-lite`) is **never called** for low-fit roles (score < 35) or known senior/lead-level mismatches.
   - We only expend costly LLM tokens on **newly observed, high-probability matches** for the candidate.
   - This hybrid pipeline reduces API token overhead by **over 88%**, lowering typical operation costs from **$0.04/job down to $0.0003/job**.

---

## 🛡️ 3. Multi-Tenant Enterprise Security (Supabase RLS)
When deploying platforms inside client tenancies, preventing data leakages (cross-tenant contamination) is critical. 

* **Row-Level Security (RLS)**: The database contains a robust RLS policy suite (`supabase/migrations/202605250002_row_level_security.sql`) restricting access.
* **Double-Guard Scoping**:
  - The PostgreSQL database enforces RLS at the database engine level based on the JWT `auth.uid()`.
  - The FastAPI service independently intercepts all headers, extracts tenant scopes, and limits database sessions to the caller's unique user identifier. It is impossible for User A to query User B's alert history, monitored boards, or profiles.

---

## 🔌 4. Graceful Degradation & Resilience (Local vs. Cloud)
Enterprise systems must remain functional even during major third-party service outages.

* **LLM Extraction Fallbacks**:
  - **Primary**: Structured response parsing via Gemini 2.5.
  - **Secondary (Local Failover)**: Ollama local extraction using `llama3:latest` for developers or laptops running locally.
  - **Tertiary (Graceful Recovery)**: Safe regex-based parser extraction if internet is down or LLM rate limits (HTTP 429) are active.
* **Notification Circuit Breakers**:
  - Telegram and SMTP alert dispatcher wraps every request in strict timeout try-catch envelopes.
  - If SMTP is unconfigured or Telegram connection times out, the notification is not lost; it is marked as `skipped_configuration` or logged with diagnostic traceback in the `AlertDelivery` telemetry logs, keeping developer debugging simple.

---

## 📊 5. Visual Diagnostics & Observability Dashboard
To prove operational capability to recruiters, the dashboard includes a custom **System Observability & Diagnostic Panel**:
- **Real-Time Integration Telemetry**: Live ping health checks for major board APIs.
- **Failover Sandbox Simulator**: An interactive playground allowing visitors to trigger simulated API connection failures (HTTP 429 / HTTP 504 / Token exhaustion) and watch the frontend recover gracefully using real-time terminal logs.
