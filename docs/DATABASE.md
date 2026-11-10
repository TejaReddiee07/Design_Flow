# Designflow database (MongoDB)

Generated from `backend/app/db/mongo.py` by `backend/scripts/export_db_docs.py`.

23 collections in the `designflow` database (name from `MONGO_DB`). Connection string from `MONGO_URI` (a MongoDB Atlas `mongodb+srv://` URI in production, `mongomock://` in the tests).

Conventions:

- Every document has an integer `_id` taken from the `counters` collection, so the API keeps the same numeric ids the frontend expects.
- `created_at` is set on insert; `updated_at` is set on insert and on every update, except in the append-only collections `agent_logs`, `analytics`, `audit_logs`, `chat_messages`, `counters`, `files`, `notifications`, `refresh_tokens`.
- All datetimes are stored in UTC and read back timezone-aware.
- Nested data (`brief`, `form_schema`, `analysis`, `messages`, `download_links`, `meta`, ...) is stored as embedded documents/arrays, not JSON strings.
- LangGraph checkpoints live in two extra collections, `langgraph_checkpoints` and `langgraph_writes`, managed by `langgraph-checkpoint-mongodb`.

## Relationships

```
users 1─1 clients (clients.user_id) 1─* projects
clients 1─* service_requests *─1 services
service_requests 1─* designs / revisions / deliveries / files / agent_logs / payments
clients 1─1 conversations 1─* chat_messages
clients 1─* brand_assets, support_tickets
lead_database 1─* outreach_history; lead_database.client_id → clients (after conversion)
users 1─* notifications, refresh_tokens, audit_logs
```

## users

Login accounts (admin, staff, client). Fields: email, password_hash, full_name, role, is_active, avatar_url, phone, timezone, last_login_at.

Passwords are bcrypt hashes. `role` is one of admin, staff, client (there is no separate roles collection). The primary admin is re-applied from `.env` on every start.

Indexes: `email asc` (unique).

## refresh_tokens

Issued refresh tokens: user_id, jti, expires_at, revoked, user_agent.

Indexes: `jti asc` (unique); `user_id asc`.

## clients

Client companies: user_id, company_name, website, industry, brand_notes, drive_folder_id, currency, status, onboarding_stage.

Indexes: `user_id asc` (unique).

## services

The design services: slug, name, category, tagline, description, long_description, turnaround_days, starting_price (USD), icon, form_schema, deliverables, is_active, sort_order.

The 19 design services. `form_schema` drives each service's request form; `starting_price` is the fixed price in USD and is converted to GBP/INR with the `FX_*` rates.

Indexes: `slug asc` (unique); `sort_order asc`.

## projects

Optional grouping of requests: client_id, name, description, status, drive_folder_id.

Indexes: `client_id asc`.

## service_requests

Design requests: client_id, project_id, service_id, title, description, brief, priority, status, submitted_at/accepted_at/started_at/review_at/completed_at/rejected_at, rejection_reason, due_at, revision_count, price_amount, price_currency, is_paid, paid_at, current_run_id, pipeline_stage, ai_summary.

`status` is the lifecycle (pending → accepted → in_progress → review → completed, or rejected); `pipeline_stage` is the agent step; `current_run_id` is the LangGraph thread id used to resume after admin approval. `brief.about_and_wishes` holds the client's own description.

Indexes: `client_id asc`; `service_id asc`; `status asc`; `submitted_at desc`.

## designs

Concept versions: request_id, version, title, concept, concept_data, file_id, preview_url, generated_by, status, qa_score, qa_notes.

Indexes: `request_id asc, version asc`.

## revisions

Client feedback rounds: request_id, design_id, round, feedback, change_items, status, submitted_by, file_ids, resolved_at.

Indexes: `request_id asc`.

## deliveries

Delivered packages: request_id, message, file_ids, download_links, delivered_by, delivered_at, version.

Indexes: `request_id asc`.

## files

Stored files: owner_user_id, client_id, request_id, kind, original_name, stored_name, backend, path, drive_file_id, public_url, mime_type, size_bytes, version, parent_file_id, checksum, meta.

Indexes: `request_id asc`; `client_id asc`.

## brand_assets

Client brand assets: client_id, type, name, file_id, value, version, meta.

Indexes: `client_id asc`.

## payments

Invoices/payments per request: client_id, request_id, amount, currency, settled_amount, settled_currency, provider, provider_payment_id, status, invoice_number, invoice_url, description, paid_at.

One invoice per request. `amount`/`currency` is what the client paid; `settled_amount`/`settled_currency` is the same amount converted to the reporting currency (INR).

Indexes: `client_id asc`; `request_id asc`; `provider_payment_id asc`.

## notifications

Per-user notifications: user_id, type, title, body, link, service_id, request_id, data, is_read, read_at.

Indexes: `user_id asc, is_read asc`; `created_at desc`.

## conversations

One chat thread per client: client_id, last_message_at, last_message_preview, admin_unread, client_unread.

Indexes: `client_id asc` (unique).

## chat_messages

Messages: conversation_id, sender_id, body, file_id, read_at.

Indexes: `conversation_id asc`.

## support_tickets

Support tickets: client_id, subject, status, priority, category, messages (list), resolved_at.

The thread is stored as a list of `{sender, name, body, at}` objects in `messages`.

Indexes: `client_id asc`; `status asc`.

## agents

The 11 AI agents: key, name, description, status, enabled, tasks_completed, tasks_failed, success_rate, last_run_at, last_error, current_activity, schedule, config, sort_order.

The 11 AI agents. `config.posts` keeps the Marketing Agent's last 20 drafts.

Indexes: `key asc` (unique).

## agent_logs

Agent steps: agent_key, run_id, request_id, level, status, step, message, input_summary, output_summary, tokens_in, tokens_out, duration_ms.

Shown in request timelines and the Control Center; pushed live over the WebSocket.

Indexes: `agent_key asc`; `request_id asc`; `created_at desc`.

## lead_database

Leads: company_name, website, industry, location, contact_name, contact_email, contact_phone, score, analysis, status, source, notes, client_id.

Leads found by the Lead Agent (source `agent`) or the contact form (source `website`). `analysis` is the agent's JSON assessment; `client_id` is set when a lead is converted.

Indexes: `contact_email asc`; `status asc`.

## outreach_history

Outreach emails: lead_id, channel, subject, body, status, sent_at, follow_up_at, follow_up_count, reply_text, generated_by.

Indexes: `lead_id asc`.

## audit_logs

Audit trail: user_id, actor, action, entity, entity_id, ip, user_agent, before, after.

Indexes: `created_at desc`; `action asc`.

## analytics

Daily metric snapshots: metric, dimension, value, date.

Daily rollups written by the `analytics_snapshot` job. `date` is the UTC midnight of the day being summarised.

Indexes: `metric asc, dimension asc, date asc` (unique).

## counters

Integer id sequences per collection.

`{_id: <collection>, seq: <int>}` — the source of every integer id.

Indexes: `_id` only.
