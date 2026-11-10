# Deployment guide

Designflow ships as four containers: `api` (FastAPI + static frontend), `worker` (agents and
scheduler), `mongo` (MongoDB 7) and `redis` (job queue and real-time pub/sub). If you use
MongoDB Atlas instead, set `MONGO_URI` in `.env` and the bundled `mongo` container is simply unused.

## 1. Prerequisites

- A Linux VPS (2 vCPU / 4 GB RAM is plenty to start) with Docker Engine and the Compose plugin.
- A domain pointing at the server (for HTTPS).
- Optional keys: Anthropic, Stripe, Google service account, SMTP credentials.

## 2. Configure

```bash
git clone <your repo> designflow && cd designflow
cp .env.example .env
```

Edit `.env`. Minimum for production:

| Variable | Set to |
|---|---|
| `APP_ENV` | `production` |
| `APP_URL` | `https://your-domain.com` |
| `SECRET_KEY` | a long random string (`openssl rand -hex 32`) |
| `MONGO_URI` | your MongoDB Atlas connection string (`mongodb+srv://user:password@cluster.mongodb.net/?retryWrites=true&w=majority`), or leave it out to use the bundled `mongo` container |
| `MONGO_DB` | database name, default `designflow` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NAME` | your login. Re-applied on every start; the app itself refuses to change them |
| `CORS_ORIGINS` | `https://your-domain.com` |

Everything else can stay in mock mode until you are ready.

## 3. Run

```bash
docker compose up -d --build
docker compose logs -f api
```

The `api` container waits for MongoDB, creates the indexes, seeds services / agents / the primary
admin (no schema migrations are needed: collections are created on first write), then starts Uvicorn on port 8000. The `worker` starts once the api is healthy.

Open `http://server-ip:8000`. Log in at `/login` with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## 4. HTTPS reverse proxy

Simplest option is Caddy on the host (automatic certificates):

```
your-domain.com {
    reverse_proxy localhost:8000
}
```

Nginx equivalent needs WebSocket headers for `/ws`:

```
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    client_max_body_size 60m;
}
```

Uvicorn runs with `--proxy-headers`, so redirects and the `Strict-Transport-Security` header work behind the proxy.

## 5. Switch integrations from mock to live

**AI model**: default is Ollama (`LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL=llama3.2:3b`). Install Ollama on the host, run `ollama pull llama3.2:3b`; in Docker set `OLLAMA_BASE_URL=http://host.docker.internal:11434`. To use Anthropic later: `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `LLM_MODEL`.

**Stripe (billing)**: set `STRIPE_SECRET_KEY`, `BILLING_PROVIDER=stripe`, add a webhook endpoint `https://your-domain.com/api/v1/billing/webhook` for `checkout.session.completed` and put its signing secret in `STRIPE_WEBHOOK_SECRET`. Each request is a one-time Checkout in the client's currency (USD, GBP or INR). Stripe pays out in **your Stripe account's own currency** (an Indian account pays out INR, a UK account GBP) and converts foreign-currency charges automatically. Payments are confirmed two ways: the webhook (production) and a direct session check when the client returns from Checkout (`POST /requests/{id}/confirm-payment`), so local testing works without a webhook. The admin dashboard reports all revenue in your payout currency (`REPORTING_CURRENCY`, GBP for a UK Stripe account; converted with `FX_GBP`/`FX_INR`), and every payment stores that equivalent (`settled_amount`, `settled_currency`). Prices per service are edited in the admin (Services) and stored in USD; `FX_GBP` / `FX_INR` derive the other currencies.

**Google Drive (storage)**:
1. In Google Cloud create a service account, enable the Drive API, download the JSON key.
2. Save it as `./secrets/gdrive-service-account.json` on the host (the compose file mounts `./secrets` read-only).
3. In your Google Drive create a root folder, share it with the service account email (Editor), copy the folder id into `GDRIVE_ROOT_FOLDER_ID`.
4. Set `STORAGE_BACKEND=gdrive`. New uploads go to Drive under `clients/<id>/requests/<id>/...`; existing local files keep working.

**Email (outreach + notifications)**: `EMAIL_PROVIDER=smtp` plus `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Works with Gmail app passwords, Resend, SendGrid, Postmark SMTP. Keep `OUTREACH_AUTO_SEND=false` so the Outreach Agent only drafts and you approve sends in the admin.

**Lead discovery**: `LEAD_PROVIDER=web` (default, free: DuckDuckGo search + site scraping) or `serpapi` with `SERPAPI_KEY` for Google Maps results.

## 6. Operations

| Task | Command |
|---|---|
| Logs | `docker compose logs -f api worker` |
| Re-create indexes + re-seed (idempotent) | `docker compose run --rm api seed` |
| Database backup (bundled mongo) | `docker compose exec mongo mongodump --archive --db designflow > backup-$(date +%F).archive` |
| Database backup (Atlas) | `mongodump --uri "$MONGO_URI" --db designflow --archive=backup-$(date +%F).archive` (Atlas also keeps its own snapshots) |
| Uploads backup (local storage) | `docker run --rm -v designflow_uploads:/data -v $PWD:/backup alpine tar czf /backup/uploads.tgz /data` |
| Scale workers | `docker compose up -d --scale worker=2` |
| Update | `git pull && docker compose up -d --build` |

Health: `GET /health` (used by the compose healthcheck). Agent health: Admin → AI Agents.

## 7. Security checklist

- `APP_ENV=production` enables HSTS and strict cookies.
- MongoDB Atlas: restrict **Network Access** to your server's IP and rotate the database user's password if it was ever shared in plain text.
- Rotate `SECRET_KEY` to invalidate all sessions.
- Rate limits: `RATE_LIMIT_DEFAULT` (120/min) and `RATE_LIMIT_AUTH` (10/min) per IP.
- Uploads: `MAX_UPLOAD_MB`, extension whitelist and content sniffing in `services/file_service.py`.
- Audit log: Admin → Audit log (every login, status change, admin edit and webhook).
- Keep `./secrets` out of git (already in `.gitignore`).

## 8. Running without Docker (development)

```bash
cd backend
python -m venv ../.venv && ../.venv/Scripts/activate   # or source ../.venv/bin/activate
pip install -r requirements.txt
set MONGO_URI=mongodb://localhost:27017                 # or your Atlas URI; export on macOS/Linux
set REDIS_URL=
python -m app.db.seed
uvicorn app.main:app --reload --port 8000
```

Without Redis the api process runs agent jobs and the scheduler in-process, so a single command
gives you the whole platform. Tests: `pytest` (uses an in-memory MongoDB via `mongomock` and the mock LLM).
