# MediCore Analytics

**Natural-language analytics over a hospital CRM**, delivered as a single-stack demo: a **FastAPI** backend, **static web UI** (Plotly dashboards + chat), and a **LangGraph**-orchestrated agent that routes questions to safe **read-only SQL** or direct answers—backed by **PostgreSQL (Supabase)** and optional **LangFuse** tracing.

---

## Table of contents

- [Overview](#overview)
- [What you get](#what-you-get)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Database](#database)
- [Run the application](#run-the-application)
- [API reference](#api-reference)
- [Testing](#testing)
- [Observability](#observability)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)

---

## Overview

MediCore models a **hospital CRM** (departments, doctors, patients, appointments, diagnoses, billing, and more). The app lets you:

1. **Explore KPI dashboards** for a date range—revenue, diagnoses, doctors, payments, and departments—with consistent chart specs.
2. **Ask questions in plain English** so an LLM pipeline can generate SQL, execute it safely, synthesize an answer, and optionally attach a **chart** built from tabular results (never arbitrary code execution).

Configuration is split between **`config/param.yaml`** / **`config/models.yaml`** (non-secret behavior) and **`.env`** (API keys and database URL).

---

## What you get

| Capability | Description |
|------------|-------------|
| **Dashboard baseline** | Five coordinated panels with declarative `ChartSpec` definitions (`src/dashboard/chart_specs.py`). |
| **Intent routing** | `QueryRouter` classifies whether to answer directly, generate SQL, or interpret prior results (`src/agents/router.py`). |
| **NL → SQL** | `NL2SQLAgent` builds prompts from live schema metadata, validates **read-only** SQL, retries on failure (`src/agents/nl2sql_agent.py`, `src/infrastructure/sql_safety.py`). |
| **Orchestration** | **LangGraph** workflow: router → NL2SQL / direct / synthesizer (`src/agents/orchestrator.py`). |
| **Multi-LLM wiring** | Router (OpenRouter), optional fast extractor path (Groq in provider module), chat/synthesis models configured in code + YAML (`src/infrastructure/llm/llm_provider.py`). |
| **Observability** | Optional **LangFuse** spans and usage metadata (`src/infrastructure/observability.py`). |

---

## Architecture

```mermaid
flowchart LR
  subgraph ui [Browser]
    SPA["Static UI · web/"]
  end

  subgraph api [FastAPI]
    GET_D["GET /api/dashboard/baseline"]
    POST_C["POST /api/chat"]
  end

  subgraph agents [LangGraph]
    R[Router]
    N[NL2SQL agent]
    D[Direct reply]
    S[Synthesizer]
  end

  subgraph data [Data]
    PG[(Supabase PostgreSQL)]
  end

  SPA --> GET_D
  SPA --> POST_C
  POST_C --> R
  R --> N
  R --> D
  R --> S
  N --> PG
  GET_D --> PG
```

---

## Tech stack

| Layer | Choices |
|-------|---------|
| **Runtime** | Python 3.10+ |
| **API** | FastAPI, Uvicorn |
| **UI** | Static HTML/CSS/JS, Plotly (CDN) |
| **Agents** | LangGraph, LangChain |
| **Database** | SQLAlchemy → PostgreSQL (connection string via `SUPABASE_DB_URL`) |
| **Config** | YAML + `pydantic-settings` / `python-dotenv` |

---

## Prerequisites

- **Python 3.10 or newer**
- A **PostgreSQL** instance reachable with a SQLAlchemy URL (the project documentation and code assume **Supabase**; any Postgres with the CRM schema loaded will work).
- API keys as required by your chosen providers (at minimum, **OpenRouter** for the router/chat path; **Groq** if you use the extractor stack as configured).

---

## Quick start

### 1. Clone and enter the project

```bash
cd "path/to/Mini Project 04"
```

### 2. Create and activate a virtual environment

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy or create a **`.env`** file in the project root (this file is gitignored). See [Configuration](#configuration) for the full variable list.

### 5. Run the server

From the **project root**, with `PYTHONPATH` set so `src` imports resolve:

**Windows (PowerShell)**

```powershell
$env:PYTHONPATH="."
uvicorn src.dashboard.fastapi_app:app --reload --host 127.0.0.1 --port 8000
```

**macOS / Linux**

```bash
export PYTHONPATH=.
uvicorn src.dashboard.fastapi_app:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in your browser.

---

## Configuration

### YAML (`config/`)

| File | Purpose |
|------|---------|
| **`param.yaml`** | Default provider, model tier, LLM defaults, logging, observability flag. |
| **`models.yaml`** | Named model IDs per provider/tier (used by config helpers). |

### Environment (`.env`)

Secrets and connection strings stay **only** in `.env`. Typical variables:

| Variable | Required for | Purpose |
|----------|----------------|----------|
| `SUPABASE_DB_URL` | Dashboard + NL2SQL | PostgreSQL URL, e.g. `postgresql://user:pass@host:5432/dbname` |
| `OPENROUTER_API_KEY` | Router / OpenRouter chat | Access to models via OpenRouter |
| `GROQ_API_KEY` | Optional | Used when Groq-backed models are enabled in `llm_provider` |
| `LANGFUSE_SECRET_KEY` | Optional tracing | LangFuse server-side secret |
| `LANGFUSE_PUBLIC_KEY` | Optional tracing | LangFuse public key |
| `LANGFUSE_BASE_URL` | Optional | Defaults to `https://us.cloud.langfuse.com` if unset |

Adjust model names and providers in **`src/infrastructure/config.py`** and **`src/infrastructure/llm/llm_provider.py`** to match your keys and routing strategy.

---

## Database

The CRM schema is defined in **`data/schema.sql`**. **`data/medicore_data.sql`** contains sample data for local or hosted Postgres.

**High-level steps:**

1. Create a database (or use Supabase).
2. Apply `data/schema.sql`, then optionally load `medicore_data.sql`.
3. Set `SUPABASE_DB_URL` (or equivalent) in `.env`.

The code expects tables such as `departments`, `doctors`, `patients`, `appointments`, `diagnoses`, `billing_invoices`, `payments`, and others—see `crm_init.py` for the checklist used at runtime.

---

## Run the application

| Endpoint | Description |
|----------|-------------|
| **`/`** | Serves **`web/index.html`** (MediCore Analytics UI). |
| **`/static/*`** | CSS, JS, and assets from **`web/`**. |
| **`/health`** | Simple `{ "status": "ok" }` health check. |
| **`/api/dashboard/baseline`** | Query params **`start`** and **`end`** (dates). Returns chart specs + panel rows for the baseline dashboard. |
| **`/api/chat`** | POST JSON body: **`message`** (string), optional **`memory`** (list of `{role, content}`). Returns status, route, answer, optional SQL/result/chart. |

The UI exposes two main views: **KPI** (date-range dashboards) and **General chat** (orchestrated Q&A).

---

## Testing

```bash
pytest
```

Integration tests that call live LLM APIs are marked **`integration`**. To skip them:

```bash
pytest -m "not integration"
```

See **`pytest.ini`** for marker definitions.

---

## Observability

When **`observability.enabled`** is `true` in `param.yaml` **and** LangFuse keys are present, traces and usage can be recorded. If keys are missing, the app logs a warning and continues without tracing—see **`src/infrastructure/observability.py`**.

---

## Project layout

```
Mini Project 04/
├── config/
│   ├── param.yaml          # Non-secret defaults
│   └── models.yaml         # Model catalog
├── data/
│   ├── schema.sql          # MediCore CRM DDL
│   └── medicore_data.sql   # Sample seed data
├── src/
│   ├── agents/             # Router, NL2SQL, orchestrator, prompts
│   ├── dashboard/          # FastAPI app, data service, Plotly helpers
│   └── infrastructure/     # Config, DB client, LLM providers, SQL safety, observability
├── tests/                  # Pytest (incl. integration)
├── traces/                 # Trace samples / notes
├── web/                    # Static frontend (index.html, styles.css, app.js)
├── requirements.txt
└── README.md
```

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| **`SUPABASE_DB_URL must be set`** | `.env` exists at project root and contains a valid Postgres URL. |
| **Import errors for `src.*`** | Run Uvicorn from project root with **`PYTHONPATH=.`** (or install package in editable mode). |
| **`web/index.html missing`** | Ensure the **`web/`** directory is present next to **`src/`**. |
| **LLM / routing errors** | Valid **`OPENROUTER_API_KEY`** (and **`GROQ_API_KEY`** if using Groq models); quota and model IDs in OpenRouter dashboard. |
| **Empty dashboard** | Date range includes data; seed **`medicore_data.sql`** if tables are empty. |

---

Built as an **AI Engineering** mini-project: end-to-end **natural language → validated SQL → insights and charts** on a realistic healthcare CRM schema, with a clean separation between **product UI**, **API**, **agents**, and **infrastructure**.
