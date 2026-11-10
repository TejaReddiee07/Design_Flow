# Designflow — AI-powered pay-per-request design platform

One web application that lets a single founder run a fixed-price design studio: public website with
19 priced services (USD, GBP, INR), client portal, admin dashboard, service management, real-time
notifications, pay-per-request billing, analytics, a web-searching Lead Agent and an AI Agent
Control Center driving a LangGraph pipeline. Built by Nagateja Goli.

```
Landing site ─ 19 service pages ─ pricing ─ contact
Client portal ─ order designs ─ pay per request ─ files ─ chat ─ invoices
Admin dashboard ─ service menu with live badges ─ request boards ─ clients ─ billing ─ leads ─ analytics
AI Agent Control Center ─ 11 agents ─ Start / Pause / Stop / Restart ─ live logs
See in live ─ watch the agents build one request step by step, in real time
```

## Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3 (design tokens, light/dark, glassmorphism), vanilla JS ES modules, hand-written canvas charts |
| Backend | Python 3.11+, FastAPI, PyMongo, Pydantic v2, WebSockets |
| Database | MongoDB (Atlas or the bundled `mongo` container; in-memory `mongomock` for tests) |
| AI | LangGraph + LangChain, **Ollama** (local, free; `llama3.2:3b` default) or Anthropic Claude; mock model when neither is reachable |
| Realtime / jobs | Redis pub/sub + queue, APScheduler, separate worker container |
| Storage | Local disk or Google Drive (service account) |
| Billing | Pay per request: fixed prices per service in USD/GBP/INR, Stripe Checkout (one-time) + webhook, mock provider until keys are added |
| Auth / security | JWT access + rotating refresh tokens, bcrypt, role guards, rate limiting, upload validation, audit log |
| Deployment | Docker Compose (api, worker, mongo, redis) |

## Quick start (Docker)

```bash
cp .env.example .env            # edit SECRET_KEY, ADMIN_* and (optionally) MONGO_URI for Atlas
docker compose up -d --build
```

Open http://localhost:8000

| Area | URL |
|---|---|
| Landing site | `/` |
| All services & prices | `/services` |
| Client portal | `/portal` (clients create their own account at `/register`) |
| Admin dashboard | `/admin` (login = `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`) |
| API docs | `/docs` |

No sample data is ever created: only the 19 services, the 11 agents and the primary admin from `.env`.
Everything else comes from real clients, requests and leads.

## Quick start (no Docker)

```bash
cd backend
python -m venv ../.venv
../.venv/Scripts/activate            # macOS/Linux: source ../.venv/bin/activate
pip install -r requirements.txt
set MONGO_URI=mongodb://localhost:27017   # or your Atlas connection string (macOS/Linux: export ...)
set REDIS_URL=
python -m app.db.seed
uvicorn app.main:app --reload
```

Without Redis the API process runs agent jobs and schedules in-process. Agents use **Ollama**
(install from https://ollama.com, then `ollama pull llama3.2:3b`); if Ollama is not running they fall back
to placeholder output so the platform still works. See `docs/DEPLOYMENT.md` to switch each
integration to live. On Windows, `run.bat` does all of the above.

## How a request flows

1. A client creates an account (choosing USD, GBP or INR), picks one of the 19 services and fills its brief, including "About your business and how you want this done". The fixed price and delivery time are shown before ordering; a pending invoice is created and the client pays (Stripe, or instantly with the mock provider).
2. On submit the admin gets a notification, the bell count and the service's badge increase instantly over WebSocket, and the card appears on the board. The Project Manager Agent writes a summary and may raise the priority.
3. The admin clicks **Accept**. The LangGraph pipeline runs on the client's brief: Project Manager → Strategy → Content → Design (renders a draft preview) → QA (scores it, loops back once if it fails). **See in live** (a button on every request card and on the request page) opens `/admin/live/<id>` in its own tab: a real-time view of the pipeline with every agent's step, the model's output as it is being written, the draft preview the moment it is rendered, the QA score, and Approve / Send back buttons.
4. The request moves to **In Review**; the admin is notified "Ready for your review". The graph is paused at the admin-approval node (LangGraph interrupt + checkpoint).
5. The admin finishes the visuals (uploads files) and clicks **Approve & deliver**, or sends it back for rework with a note. On approval the Delivery Agent packages files, creates download links and notifies the client. Status → **Completed**.
6. The client can download, or request a revision. The Revision Agent converts feedback into a change list and the request re-enters Design → QA → review.

The admin can also skip the agents entirely: Accept, work manually, upload files, click **Completed**.

## Files: Client files (admin) and Your designs (client)

- **Client files** (admin sidebar): one folder per client, named after the company. Open a folder to see every service
  they ordered, each request, every draft version and every delivery, with previews, a lightbox and per-file or ZIP downloads.
- **Your designs** (client portal): appears as soon as the admin clicks **Approve & deliver**. The client sees their delivered
  designs grouped by service and can download each file or everything as one ZIP.
- On disk (or Google Drive) the same structure is used: `clients/<Company> #<id>/<Service>/Request <id> - <title>/Drafts|Final`.

## Leads

The Lead Agent searches the web (DuckDuckGo, no API key) for businesses that buy each kind of service, opens their sites,
extracts a contact email and scores them. New leads notify the admin and the Outreach Agent drafts a personalised email
(sent through your SMTP once approved). Website contact-form enquiries become leads too. **Convert to client** turns a lead
into a client account plus a request for the design they asked for, emails them their login, and the normal pipeline takes over.

## Project structure

```
backend/
  app/
    main.py              FastAPI app, middleware, static hosting
    core/                config, security (JWT/bcrypt), deps, rate limit, audit, events (Redis/WS), jobs, plans
    db/                  mongo (client, repositories, indexes, counters), seed, seed_data (19 services + 11 agents)
    models/              enums (roles, statuses, priorities)
    schemas/             Pydantic request/response models
    api/v1/              routers: auth, clients, projects, services, requests, files, notifications,
                         chat, support, contact, billing, leads/outreach, agents, analytics, admin, ws
    services/            request lifecycle, notifications, files, storage (local/gdrive), billing (stripe/mock), email
    agents/              llm factory, control plane, nodes (11 agents), graphs (LangGraph), pipelines, runner, scheduler
    worker.py            worker process entry point
  scripts/               entrypoint, wait_for_db, export_api_docs, export_db_docs, generate_service_pages
  tests/                 pytest suite (auth, requests, platform, realtime, agents, billing webhook)
frontend/
  index.html             landing page
  services/              19 generated service pages + index
  login.html, register.html, legal/
  portal/index.html      client portal (hash router SPA)
  admin/index.html       admin dashboard (hash router SPA)
  assets/css/            tokens, base, components, landing, portal, admin
  assets/js/core/        api, auth, ws, router, store, ui, charts
  assets/js/landing|portal|admin/
docs/                    API.md, DATABASE.md, AGENTS.md, DEPLOYMENT.md
docker-compose.yml, Dockerfile, .env.example
```

## Tests

```bash
cd backend && pytest
```

The suite boots the app against an in-memory MongoDB (`mongomock`) with the mock LLM and covers authentication,
the request lifecycle and action buttons, file security, notifications, WebSocket push, chat,
billing (mock checkout and Stripe webhook events), the agent control buttons and the full
LangGraph pipeline including approval, rework and revisions.

## Regenerating docs and pages

```bash
cd backend
python scripts/generate_service_pages.py   # 19 service pages + services-data.js from seed_data.py
python scripts/export_api_docs.py          # docs/API.md
python scripts/export_db_docs.py           # docs/DATABASE.md
```

## Documentation

- `docs/API.md` – every endpoint and the WebSocket event types
- `docs/DATABASE.md` – MongoDB collections, fields and indexes
- `docs/AGENTS.md` – agents, workflows, control center
- `docs/DEPLOYMENT.md` – production setup, integrations, operations
- `PROJECT_PLAN.txt` – the original build plan and decisions
