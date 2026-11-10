# AI agents and LangGraph workflows

Designflow runs eleven agents. They are plain Python functions ("nodes") orchestrated by
LangGraph graphs, with a control plane (status, metrics, logs, Start / Pause / Stop / Restart)
stored in the `agents` and `agent_logs` collections and streamed live to the admin Control Center.

Code: `backend/app/agents/`

| Path | What it is |
|---|---|
| `llm.py` | Model factory. `ChatOllama` (local, free) by default, `ChatAnthropic` when `LLM_PROVIDER=anthropic` and a key is set, otherwise a deterministic `MockLLM` so everything still runs. |
| `control.py` | Control plane: `running()` context manager wraps every unit of work with pause/stop checks, status broadcast, timing, token counts and metrics. |
| `nodes/` | One file per agent. |
| `graphs/request_pipeline.py` | The main workflow (below). |
| `graphs/lead_pipeline.py`, `onboarding_graph.py`, `marketing_graph.py` | Smaller workflows. |
| `graphs/checkpoint.py` | LangGraph checkpointer: MongoDB (`langgraph_checkpoints` / `langgraph_writes` collections); in-memory under the test-suite. |
| `pipelines.py` | Registers every background job type (`request_pipeline`, `request_resume`, `revision_pipeline`, `project_manager_triage`, `onboarding`, `lead_generation`, `outreach_draft`, `outreach_followups`, `marketing_posts`, `analytics_snapshot`). |
| `runner.py` | Job dispatcher used by the worker process and the in-process fallback. |
| `scheduler.py` | APScheduler cron jobs for Lead, Outreach follow-ups, Marketing and the daily analytics snapshot. |
| `tools/` | Website fetcher, lead discovery providers (mock / SerpAPI), draft renderer (SVG concept cards). |

## The request pipeline

```
Client request ──► Project Manager ──► Strategy ──► Content ──► Design ──► QA
                                                                   ▲          │ fail (max 2)
                                                                   └──────────┘
                                                            pass ▼
                                                     Request review (status = review,
                                                     admin notified "Ready for your review")
                                                            ▼
                                              ┌── [interrupt] Admin approval ──┐
                                              │ approved                       │ rework
                                              ▼                                ▼
                                           Delivery ──► Complete            Design ──► QA ──► review …
Revision (client feedback) ──► Design ──► QA ──► review ──► approval ──► Delivery
```

Implementation notes:

- The graph is compiled with `interrupt_before=["admin_approval"]` and a checkpointer. The
  thread id is the request's `current_run_id`. When the admin clicks **Approve & deliver**
  (`POST /requests/{id}/approve`) the API enqueues `request_resume`; the worker calls
  `graph.update_state(config, {"approved": True, ...})` then `graph.invoke(None, config)`,
  which continues from the saved checkpoint into Delivery.
- If no checkpoint exists (for example the API restarted while using the in-memory
  checkpointer), `resume_pipeline` falls back to a small "resume graph" that starts at the
  approval node using state rebuilt from the database. With MongoDB the checkpoint survives
  restarts and works across the api and worker containers.
- `approved=false` sends the request back to Design with the admin's note; QA runs again and the
  request returns to review.
- Every node reads and writes through the MongoDB repositories, updates `service_requests.pipeline_stage`, and
  wraps its work in `control.running(...)`, which:
  - waits while the agent is **paused**, aborts with `AgentStopped` when it is **stopped**,
  - sets status to running and broadcasts `agent_status`,
  - writes `agent_logs` documents (`started`, `completed` / `failed` / `skipped`) with duration and tokens,
  - updates `tasks_completed`, `tasks_failed`, `success_rate`, `last_run_at`.

## Design engine (what the Design Agent produces)

`backend/app/agents/tools/design_engine/` turns each request into finished deliverables for its service, built from
what the client wrote: the request form, their uploaded logo and brand colours, photos attached to the request, the
Strategy and Content agents' output, and any rework/revision feedback ("warmer", "darker", "bigger headline", "use navy").

| Module | Role |
|---|---|
| `brand.py` | Brand kit: palette from the brief (hex codes or colour words), style, font pairing, industry motif, feedback tweaks |
| `fonts.py`, `canvas.py` | Real typography: HarfBuzz shaping with kerning, glyphs drawn as vector outlines (13 open-licence fonts in `app/assets/fonts`) |
| `marks.py`, `icons.py` | Logo constructions (emblem, icon + wordmark, monogram, wordmark) and 50 hand-built vector icons |
| `svc_logo.py` | 3 logo concepts, full logo suite (colour, reversed, black, white, icon, app icon), 7-page brand guidelines PDF |
| `svc_social.py` | Feed posts (portrait, square, story), carousels, Reels covers, YouTube A/B thumbnails, ad sets in every placement |
| `svc_decks.py` | Pitch decks and presentations (16:9 slides + PDF) |
| `svc_print.py` | Flyers, posters, brochures, infographics, business cards, company profiles (3 mm bleed, 300 dpi print PDFs) |
| `svc_misc.py` | Website banners (+ retina @2x), e-commerce listing images + A+ modules, product ads, custom requests |
| `export.py` | SVG to PNG (resvg), JPEG previews, multi-page PDF, ZIP |

Every version is stored in the client's own folder:
`clients/<Company> #<id>/<Service>/Request <id> - <title>/Drafts/v<n>/...` and the delivered package in `.../Final/`.
The design document lists every file (`files`), a presentation board (`file_id`) and the version ZIP (`package_file_id`).

## Live feed ("See in live")

Every agent step is also written to the `pipeline_events` collection and pushed over the WebSocket as a
`pipeline_event` (`pipeline_started`, `agent_started`, `agent_completed` with the full model output,
`design_rendered`, `qa_scored`, `awaiting_approval`, `approved` / `rework`, `delivered`, `completed`,
`failed`, `stopped`). While a model is writing, `llm.complete()` streams partial text as `agent_stream`
events (not stored). `app/agents/live.py` holds both helpers; `control.running()` emits the start/finish
events and sets the stream context, so nodes only add their own domain events.

The admin page `/admin/live/<request id>` (`frontend/admin/live.html`, `assets/js/admin/live.js`) loads
`GET /requests/{id}/live` (request detail, pipeline agents, stored events, recent logs, model in use) and then
follows the socket: a pipeline stepper, the "working now" panel with the streamed output, the chronological
feed, the design preview with QA score, and Approve & deliver / Send back (`POST /requests/{id}/rework`)
buttons. Clients who own the request may open the same page.

## Agents

| Agent | Key | Trigger | What it does | Output |
|---|---|---|---|---|
| Lead Agent | `lead` | Cron (`LEAD_AGENT_CRON`), "Run now", `POST /leads/generate` | Searches the web (DuckDuckGo) for businesses that buy a given service, opens their sites, extracts a contact email, scores fit 0-100 | `lead_database` rows, admin notification, outreach drafts queued |
| Outreach Agent | `outreach` | `POST /outreach/draft`, follow-up cron | Writes a personalised email per lead; follow-ups after 3 days (max 2) | `outreach_history` drafts; sent automatically only when `OUTREACH_AUTO_SEND=true`, otherwise approved in admin |
| Onboarding Agent | `onboarding` | Client registration | Creates the client folder (local or Drive), welcome chat message, asset checklist ticket | Client stage → `assets_requested` |
| Project Manager Agent | `project_manager` | Request submitted (triage) and pipeline start | Summary, suggested priority (only ever raised), task plan | `ai_summary`, `priority` |
| Strategy Agent | `strategy` | Pipeline | Positioning, audience insights, competitor notes, creative direction | state `strategy` |
| Content Agent | `content` | Pipeline | Headlines, sub-headlines, body copy, CTAs, captions, hashtags | state `content` |
| Design Agent | `design` | Pipeline, rework, revision | Two concept directions; renders a draft preview (SVG concept card by default; plug a real image API in `tools/images.py`) | `designs` row (+ `files` preview) |
| QA Agent | `qa` | Pipeline | Scores the concept against brief + brand, lists issues; pass at ≥ 80 | `designs.qa_score`, `qa_notes` |
| Delivery Agent | `delivery` | After approval | Packages design previews, admin-uploaded files and a delivery-notes file; creates download links; notifies the client | `deliveries` row, status → completed |
| Revision Agent | `revision` | Client revision request | Turns feedback into a concrete change list, re-enters the pipeline | `revisions.change_items` |
| Marketing Agent | `marketing` | Cron (`MARKETING_AGENT_CRON`), "Run now" | Writes LinkedIn / Instagram / X posts from this week's real numbers | `agents.config.posts`, admin notification |

## Control Center actions

`POST /agents/{key}/start|pause|stop|restart|run`

- **Pause**: running work finishes its current LLM call then waits before the next step (up to 1 h).
- **Stop**: the agent is disabled; any pipeline reaching it aborts cleanly (`agent_logs` status `skipped`, request `pipeline_stage = stopped`). Press **Start** or **Restart** to re-enable and use *Run pipeline* on the request to continue.
- **Run now**: queues the agent's job (`MANUAL_JOBS` in `api/v1/agents.py`). Pipeline agents need a `request_id`.
- Schedules (cron, UTC) are editable per agent (`PATCH /agents/{key}`); the scheduler reloads every 10 minutes.

## Models and cost

- Default provider: **Ollama** (`LLM_PROVIDER=ollama`, `OLLAMA_MODEL=llama3.1`). Free and local; the first request after a cold start is slow while the model loads.
- Anthropic later: `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `LLM_MODEL` (default `claude-sonnet-5-5`), per-agent `LLM_MODEL_<KEY>`.
- Neither reachable: mock output, clearly logged, so the UI keeps working.
- Each pipeline run makes 5 LLM calls (6 with rework). Token counts are recorded per step in `agent_logs`.

## Adding an agent

1. Add the key to `AGENT_KEYS` in `models/enums.py` and a row in `db/seed_data.py` (`AGENTS`).
2. Create `nodes/<key>.py` with a `node(state)` or `run(...)` function wrapped in `control.running`.
3. Add it to a graph in `graphs/` (or a new one) and register a job in `pipelines.py`.
4. Map the "Run now" job in `MANUAL_JOBS` (`api/v1/agents.py`). The Control Center renders it automatically.
