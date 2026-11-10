# Designflow API reference

Generated from the OpenAPI schema by `backend/scripts/export_api_docs.py`. Interactive docs: `/docs` (Swagger UI) and `/redoc`.

Base URL: `/api/v1`. Authentication: `Authorization: Bearer <access_token>` (obtain via `POST /auth/login`).
Errors use `{ "detail": "message" }`; validation errors return HTTP 422 with a list of field errors.

## Real-time WebSocket

`GET /ws?token=<access_token>` upgrades to a WebSocket. Messages are JSON `{type, payload}`:

| type | audience | payload |
|---|---|---|
| `hello` | the connecting user | `{user_id, role, unread_count}` |
| `notification` | one user | `{notification, unread_count}` |
| `unread_count` | one user | `{unread_count}` |
| `badge_counts` | admins | `{services: [{id, slug, name, pending}], total_pending, highlight_service_id}` |
| `request_update` | admins + the request's client | `{request_id, status, service_id, client_id, pipeline_stage, title, event}` |
| `chat_message` | both parties | `{conversation_id, message}` |
| `agent_status` | admins | `{agent}` |
| `agent_log` | admins | `{agent_key, run_id, request_id, step, status, message, created_at}` |

Send `{"type": "ping"}` to keep the connection alive; the server also pings idle connections every 45 s.

## Auth

Register, log in, refresh and manage the current user. Access tokens last 15 minutes; refresh tokens are rotated on every refresh and revoked on logout.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `POST` | `/auth/register` | Register | `RegisterIn` | `TokenOut` |
| `POST` | `/auth/login` | Login | `LoginIn` | `TokenOut` |
| `POST` | `/auth/refresh` | Refresh | `RefreshIn` | `TokenOut` |
| `POST` | `/auth/logout` | Logout | `RefreshIn` | `Msg` |
| `GET` | `/auth/me` | Me |  | `UserOut` |
| `PATCH` | `/auth/me` | Update Me | `ProfileUpdate` | `UserOut` |
| `POST` | `/auth/change-password` | Change Password | `PasswordChange` | `Msg` |

## Clients

Admin management of client accounts. Clients may read their own profile via `/clients/me`.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/clients` | List Clients (query: q, status, page, page_size) |  | `Page_ClientOut_` |
| `POST` | `/clients` | Create Client | `ClientCreate` | `ClientOut` |
| `GET` | `/clients/me` | My Client |  | `ClientOut` |
| `GET` | `/clients/{client_id}` | Get Client |  | `ClientOut` |
| `PATCH` | `/clients/{client_id}` | Update Client | `ClientUpdate` | `ClientOut` |
| `DELETE` | `/clients/{client_id}` | Delete Client |  |  |
| `GET` | `/clients/{client_id}/overview` | Client Overview |  | `ClientOverview` |

## Projects

Optional grouping of requests. Clients see only their own projects.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/projects` | List Projects (query: client_id) |  | `list[ProjectOut]` |
| `POST` | `/projects` | Create Project | `ProjectCreate` | `ProjectOut` |
| `GET` | `/projects/{project_id}` | Get Project |  | `ProjectOut` |
| `PATCH` | `/projects/{project_id}` | Update Project | `ProjectUpdate` | `ProjectOut` |
| `DELETE` | `/projects/{project_id}` | Delete Project |  |  |

## Services

The 19 design services, their request forms (`form_schema`), fixed prices in USD/GBP/INR, pending-count badges and per-service analytics.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/services` | List Services (query: include_inactive) |  | `list[ServiceOut]` |
| `GET` | `/services/counts` | Pending Counts |  |  |
| `GET` | `/services/{slug}` | Get Service |  | `ServiceOut` |
| `PATCH` | `/services/{service_id}` | Update Service | `ServiceUpdate` | `ServiceOut` |
| `GET` | `/services/{service_id}/requests` | Service Requests (query: status, limit) |  | `list[RequestOut]` |
| `GET` | `/services/{service_id}/analytics` | Service Analytics |  | `ServiceAnalytics` |

## Requests

The core object. Includes the action buttons (accept / reject / complete), pipeline triggers, designs, revisions and deliveries.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/requests` | List Requests (query: status, service_id, client_id, project_id, priority, q, page, page_size) |  | `Page_RequestOut_` |
| `POST` | `/requests` | Create Request | `RequestCreate` | `RequestOut` |
| `GET` | `/requests/{request_id}` | Get Request |  | `RequestDetail` |
| `PATCH` | `/requests/{request_id}` | Update Request | `RequestUpdate` | `RequestOut` |
| `DELETE` | `/requests/{request_id}` | Delete Request |  |  |
| `POST` | `/requests/{request_id}/accept` | Accept |  | `RequestOut` |
| `POST` | `/requests/{request_id}/reject` | Reject | `RejectIn` | `RequestOut` |
| `POST` | `/requests/{request_id}/complete` | Complete |  | `RequestOut` |
| `POST` | `/requests/{request_id}/start` | Start |  | `RequestOut` |
| `POST` | `/requests/{request_id}/review` | To Review |  | `RequestOut` |
| `POST` | `/requests/{request_id}/status` | Set Status | `StatusIn` | `RequestOut` |
| `POST` | `/requests/{request_id}/run-pipeline` | Run Pipeline |  | `RequestOut` |
| `POST` | `/requests/{request_id}/approve` | Approve (query: design_id, message) |  | `RequestOut` |
| `POST` | `/requests/{request_id}/rework` | Rework (query: message) |  | `RequestOut` |
| `GET` | `/requests/{request_id}/live` | Live State (query: since_id) |  |  |
| `POST` | `/requests/{request_id}/pay` | Pay |  |  |
| `POST` | `/requests/{request_id}/confirm-payment` | Confirm Payment (query: session_id) |  |  |
| `POST` | `/requests/{request_id}/mark-paid` | Mark Paid (query: note) |  | `RequestOut` |
| `GET` | `/requests/{request_id}/designs` | Designs |  | `list[DesignOut]` |
| `POST` | `/requests/{request_id}/designs` | Add Design | `DesignCreate` | `DesignOut` |
| `POST` | `/requests/{request_id}/designs/{design_id}/approve` | Approve Design |  | `DesignOut` |
| `GET` | `/requests/{request_id}/revisions` | Revisions |  | `list[RevisionOut]` |
| `POST` | `/requests/{request_id}/revisions` | Request Revision | `RevisionCreate` | `RevisionOut` |
| `PATCH` | `/requests/{request_id}/revisions/{revision_id}` | Update Revision (query: status) |  | `RevisionOut` |
| `GET` | `/requests/{request_id}/deliveries` | Deliveries |  | `list[DeliveryOut]` |
| `POST` | `/requests/{request_id}/deliveries` | Create Delivery | `DeliveryCreate` | `DeliveryOut` |

## Files

Secure uploads (type whitelist, size limit, content sniffing), downloads, version chains and brand assets.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `POST` | `/files/upload` | Upload | multipart form |  |
| `GET` | `/files` | List Files (query: request_id, client_id, kind, limit) |  |  |
| `GET` | `/files/{file_id}` | File Meta |  |  |
| `DELETE` | `/files/{file_id}` | Delete File |  |  |
| `GET` | `/files/{file_id}/versions` | Versions |  |  |
| `GET` | `/files/{file_id}/download` | Download |  |  |
| `GET` | `/brand-assets` | List Assets (query: client_id) |  | `list[BrandAssetOut]` |
| `POST` | `/brand-assets` | Create Asset | `BrandAssetIn` | `BrandAssetOut` |
| `DELETE` | `/brand-assets/{asset_id}` | Delete Asset |  |  |

## Notifications

Per-user notification stream with unread counts; pushed live over the WebSocket as well.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/notifications` | List Notifications (query: unread_only, service_id, type, limit, offset) |  | `list[NotificationOut]` |
| `GET` | `/notifications/unread-count` | Unread |  |  |
| `POST` | `/notifications/mark-read` | Mark Read | `MarkReadIn` |  |
| `POST` | `/notifications/{notification_id}/read` | Mark One |  |  |
| `POST` | `/notifications/mark-all-read` | Mark All |  |  |
| `DELETE` | `/notifications/{notification_id}` | Delete Notification |  |  |

## Chat

Client to admin messaging with file attachments and live delivery.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/chat/conversations` | Conversations |  | `list[ConversationOut]` |
| `GET` | `/chat/messages` | Messages (query: conversation_id, client_id, before_id, limit) |  | `list[ChatMessageOut]` |
| `POST` | `/chat/messages` | Send Message (query: conversation_id, client_id) | `ChatMessageIn` | `ChatMessageOut` |

## Support

Support tickets with threaded replies.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/support/tickets` | List Tickets (query: status) |  | `list[TicketOut]` |
| `POST` | `/support/tickets` | Create Ticket | `TicketCreate` | `TicketOut` |
| `GET` | `/support/tickets/{ticket_id}` | Get Ticket |  | `TicketOut` |
| `PATCH` | `/support/tickets/{ticket_id}` | Update Ticket (query: status) |  | `TicketOut` |
| `POST` | `/support/tickets/{ticket_id}/reply` | Reply | `TicketReply` | `TicketOut` |

## Public

Unauthenticated endpoints used by the landing page.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `POST` | `/public/contact` | Contact | `ContactIn` |  |
| `GET` | `/public/services-pricing` | Services Pricing |  |  |

## Billing

Pay-per-request checkout (Stripe or mock), payment confirmation, invoices, manual payments and the Stripe webhook. Amounts are settled in the reporting currency (INR).

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/billing/currencies` | Currencies |  |  |
| `GET` | `/billing/invoices` | My Invoices |  | `list[PaymentOut]` |
| `GET` | `/billing/summary` | Summary |  |  |
| `GET` | `/billing/payments` | List Payments (query: client_id, status, page, page_size) |  | `Page_PaymentOut_` |
| `POST` | `/billing/payments` | Manual Payment | `ManualPaymentIn` | `PaymentOut` |
| `POST` | `/billing/payments/{payment_id}/mark-paid` | Mark Payment Paid |  | `PaymentOut` |
| `POST` | `/billing/webhook` | Webhook |  |  |

## Leads

Lead database and outreach history, including Lead Agent triggers and email sending.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/leads` | List Leads (query: status, q, min_score, page, page_size) |  | `Page_LeadOut_` |
| `POST` | `/leads` | Create Lead | `LeadCreate` | `LeadOut` |
| `GET` | `/leads/stats` | Lead Stats |  |  |
| `POST` | `/leads/generate` | Generate | `LeadGenerateIn` |  |
| `POST` | `/leads/{lead_id}/convert` | Convert Lead | `LeadConvertIn` |  |
| `GET` | `/leads/{lead_id}` | Get Lead |  | `LeadOut` |
| `PATCH` | `/leads/{lead_id}` | Update Lead | `LeadUpdate` | `LeadOut` |
| `DELETE` | `/leads/{lead_id}` | Delete Lead |  |  |
| `GET` | `/leads/{lead_id}/outreach` | Lead Outreach |  | `list[OutreachOut]` |
| `GET` | `/outreach` | List Outreach (query: status, page, page_size) |  | `Page_OutreachOut_` |
| `POST` | `/outreach/draft` | Draft | `OutreachDraftIn` |  |
| `POST` | `/outreach/send` | Send | `OutreachSendIn` |  |
| `GET` | `/outreach/settings` | Outreach Settings |  |  |
| `PATCH` | `/outreach/{outreach_id}` | Update Outreach (query: status, subject, body, reply_text) |  | `OutreachOut` |

## Agents

AI Agent Control Center: status, metrics, logs, Start / Pause / Stop / Restart / Run.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/agents` | List Agents |  | `list[AgentOut]` |
| `GET` | `/agents/summary` | Summary |  |  |
| `GET` | `/agents/logs` | All Logs (query: agent_key, request_id, run_id, level, limit) |  | `list[AgentLogOut]` |
| `GET` | `/agents/{key}` | Get Agent |  | `AgentOut` |
| `PATCH` | `/agents/{key}` | Configure | `AgentConfigIn` | `AgentOut` |
| `GET` | `/agents/{key}/logs` | Agent Logs (query: limit) |  | `list[AgentLogOut]` |
| `GET` | `/agents/{key}/stats` | Agent Stats |  |  |
| `POST` | `/agents/{key}/{action}` | Agent Action | `object` | `AgentOut` |

## Analytics

Dashboard numbers for admins (overview, revenue, requests, agents, leads) and clients (my-stats).

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/analytics/overview` | Overview |  |  |
| `GET` | `/analytics/revenue` | Revenue (query: months) |  |  |
| `GET` | `/analytics/requests` | Requests Analytics (query: days) |  |  |
| `GET` | `/analytics/agents` | Agents Analytics (query: days) |  |  |
| `GET` | `/analytics/leads` | Leads Analytics (query: days) |  |  |
| `GET` | `/analytics/sales` | Sales Analytics |  |  |
| `GET` | `/analytics/my-stats` | My Stats |  |  |

## Admin

Users, roles, audit log and system settings.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/admin/users` | Users (query: role) |  | `list[AdminUserOut]` |
| `POST` | `/admin/users` | Create User | `AdminUserCreate` | `AdminUserOut` |
| `PATCH` | `/admin/users/{user_id}` | Update User | `AdminUserUpdate` | `AdminUserOut` |
| `GET` | `/admin/roles` | Roles |  |  |
| `GET` | `/admin/audit` | Audit Log (query: action, entity, user_id, page, page_size) |  | `Page_AuditOut_` |
| `GET` | `/admin/settings` | System Settings |  |  |

## System

Health check.

| Method | Path | Description | Body | Response |
|---|---|---|---|---|
| `GET` | `/health` | Health |  |  |

## Schemas

Request and response models (field: type). Optional fields are marked with `?`.

**AdminUserCreate** - email: string, password: string, full_name: string, role?: string

**AdminUserOut** - id: integer, email: string, full_name: string, role?: string, is_active: boolean, last_login_at?: string, created_at?: string

**AdminUserUpdate** - full_name?: string, role?: string, is_active?: boolean, password?: string

**AgentConfigIn** - schedule?: string, enabled?: boolean, config?: object

**AgentLogOut** - id: integer, agent_key: string, run_id?: string, request_id?: integer, level: string, status: string, step?: string, message: string, input_summary?: string, output_summary?: string, tokens_in: integer, tokens_out: integer, duration_ms: integer, created_at?: string

**AgentOut** - id: integer, key: string, name: string, description?: string, status: string, enabled: boolean, tasks_completed: integer, tasks_failed: integer, success_rate: number, last_run_at?: string, last_error?: string, current_activity?: string, schedule?: string, config?: object, sort_order: integer

**AgentRunIn** - payload?: object

**AuditOut** - id: integer, user_id?: integer, actor: string, action: string, entity: string, entity_id?: integer, ip?: string, before?: object, after?: object, created_at?: string

**Body_upload_api_v1_files_upload_post** - file: string, request_id?: integer, kind?: string, client_id?: integer, parent_file_id?: integer

**BrandAssetIn** - type: string, name: string, file_id?: integer, value?: string, client_id?: integer

**BrandAssetOut** - id: integer, client_id: integer, type: string, name: string, file_id?: integer, value?: string, version: integer, meta?: object, download_url?: string, created_at?: string

**ChatMessageIn** - body?: string, file_id?: integer

**ChatMessageOut** - id: integer, conversation_id: integer, sender_id: integer, sender_name?: string, sender_role?: string, body?: string, file_id?: integer, file_name?: string, read_at?: string, created_at?: string

**ClientBrief** - id: integer, company_name: string, website?: string, industry?: string, currency?: string, status: string, onboarding_stage: string

**ClientCreate** - email: string, password: string, full_name: string, company_name: string, website?: string, industry?: string, brand_notes?: string, currency?: string

**ClientOut** - id: integer, user_id: integer, email?: string, full_name?: string, company_name: string, website?: string, industry?: string, brand_notes?: string, drive_folder_id?: string, currency?: string, status: string, onboarding_stage: string, active_requests?: integer, unpaid_requests?: integer, total_requests?: integer, total_paid?: number, created_at?: string, last_login_at?: string

**ClientOverview** - client: ref, requests_by_status: object, recent_requests: list[object], payments: list[object], brand_assets: list[object], projects: list[object]

**ClientUpdate** - company_name?: string, website?: string, industry?: string, brand_notes?: string, currency?: string, status?: string, onboarding_stage?: string, drive_folder_id?: string, is_active?: boolean

**ContactIn** - name: string, email: string, company?: string, website?: string, message: string, service?: string

**ConversationOut** - id: integer, client_id: integer, company_name: string, client_name: string, last_message_at?: string, last_message_preview?: string, unread?: integer

**DeliveryCreate** - message?: string, file_ids?: list[integer], mark_completed?: boolean

**DeliveryOut** - id: integer, request_id: integer, message?: string, file_ids?: list[integer], download_links?: list[object], delivered_by: string, delivered_at?: string, version: integer

**DesignCreate** - title?: string, concept?: string, concept_data?: object, file_id?: integer, preview_url?: string

**DesignOut** - id: integer, request_id: integer, version: integer, title?: string, concept?: string, concept_data?: object, file_id?: integer, preview_url?: string, generated_by: string, status: string, qa_score?: number, qa_notes?: string, created_at?: string

**FileOut** - id: integer, kind: string, original_name: string, mime_type: string, size_bytes: integer, version: integer, public_url?: string, request_id?: integer, created_at?: string, download_url?: string

**HTTPValidationError** - detail?: list[ValidationError]

**LeadConvertIn** - service_slug?: string, title?: string, description?: string, currency?: string, password?: string, send_email?: boolean

**LeadCreate** - company_name: string, website?: string, industry?: string, location?: string, contact_name?: string, contact_email?: string, contact_phone?: string, notes?: string, score?: integer

**LeadGenerateIn** - industry?: string, location?: string, count?: integer, service_slug?: string

**LeadOut** - id: integer, company_name: string, website?: string, industry?: string, location?: string, contact_name?: string, contact_email?: string, contact_phone?: string, score: integer, analysis?: object, status: string, source: string, notes?: string, client_id?: integer, outreach_count?: integer, created_at?: string

**LeadUpdate** - status?: string, notes?: string, score?: integer, contact_name?: string, contact_email?: string, industry?: string

**LoginIn** - email: string, password: string

**ManualPaymentIn** - client_id: integer, amount: number, description?: string, status?: string, request_id?: integer, currency?: string

**MarkReadIn** - ids?: list[integer]

**Msg** - ok?: boolean, message?: string, data?: object

**NotificationOut** - id: integer, type: string, title: string, body?: string, link?: string, service_id?: integer, request_id?: integer, data?: object, is_read: boolean, created_at?: string

**OutreachDraftIn** - lead_ids: list[integer], tone?: string

**OutreachOut** - id: integer, lead_id: integer, company_name?: string, contact_email?: string, channel: string, subject?: string, body: string, status: string, sent_at?: string, follow_up_at?: string, follow_up_count: integer, reply_text?: string, generated_by: string, created_at?: string

**OutreachSendIn** - outreach_ids: list[integer]

**Page_AuditOut_** - items: list[AuditOut], total: integer, page: integer, page_size: integer

**Page_ClientOut_** - items: list[ClientOut], total: integer, page: integer, page_size: integer

**Page_LeadOut_** - items: list[LeadOut], total: integer, page: integer, page_size: integer

**Page_OutreachOut_** - items: list[OutreachOut], total: integer, page: integer, page_size: integer

**Page_PaymentOut_** - items: list[PaymentOut], total: integer, page: integer, page_size: integer

**Page_RequestOut_** - items: list[RequestOut], total: integer, page: integer, page_size: integer

**PasswordChange** - current_password: string, new_password: string

**PaymentOut** - id: integer, client_id: integer, company_name?: string, subscription_id?: integer, request_id?: integer, request_title?: string, amount: number, currency: string, settled_amount?: number, settled_currency?: string, provider: string, status: string, invoice_number?: string, invoice_url?: string, description?: string, paid_at?: string, created_at?: string

**ProfileUpdate** - full_name?: string, phone?: string, timezone?: string, avatar_url?: string, company_name?: string, website?: string, industry?: string, brand_notes?: string, currency?: string

**ProjectCreate** - name: string, description?: string, client_id?: integer

**ProjectOut** - id: integer, client_id: integer, company_name?: string, name: string, description?: string, status: string, drive_folder_id?: string, request_count?: integer, created_at?: string

**ProjectUpdate** - name?: string, description?: string, status?: string

**RefreshIn** - refresh_token: string

**RegisterIn** - email: string, password: string, full_name: string, company_name: string, website?: string, industry?: string, currency?: string

**RejectIn** - reason?: string

**RequestCreate** - service_id?: integer, service_slug?: string, project_id?: integer, title: string, description?: string, brief?: object, priority?: ref, file_ids?: list[integer], client_id?: integer

**RequestDetail** - id: integer, client_id: integer, client_name?: string, company_name?: string, project_id?: integer, project_name?: string, service_id: integer, service_name?: string, service_slug?: string, title: string, description?: string, brief?: object, priority: string, status: string, pipeline_stage?: string, ai_summary?: string, submitted_at?: string, accepted_at?: string, started_at?: string, review_at?: string, completed_at?: string, rejected_at?: string, rejection_reason?: string, due_at?: string, revision_count?: integer, price_amount?: number, price_currency?: string, is_paid?: boolean, paid_at?: string, turnaround_days?: integer, created_at?: string, updated_at?: string, designs?: list[DesignOut], revisions?: list[RevisionOut], deliveries?: list[DeliveryOut], files?: list[FileOut], timeline?: list[object]

**RequestOut** - id: integer, client_id: integer, client_name?: string, company_name?: string, project_id?: integer, project_name?: string, service_id: integer, service_name?: string, service_slug?: string, title: string, description?: string, brief?: object, priority: string, status: string, pipeline_stage?: string, ai_summary?: string, submitted_at?: string, accepted_at?: string, started_at?: string, review_at?: string, completed_at?: string, rejected_at?: string, rejection_reason?: string, due_at?: string, revision_count?: integer, price_amount?: number, price_currency?: string, is_paid?: boolean, paid_at?: string, turnaround_days?: integer, created_at?: string, updated_at?: string

**RequestUpdate** - title?: string, description?: string, brief?: object, priority?: ref, project_id?: integer, due_at?: string

**RevisionCreate** - feedback: string, design_id?: integer, file_ids?: list[integer]

**RevisionOut** - id: integer, request_id: integer, design_id?: integer, round: integer, feedback: string, change_items?: list[], status: string, file_ids?: list[integer], created_at?: string, resolved_at?: string

**ServiceAnalytics** - service_id: integer, slug: string, name: string, total: integer, by_status: object, avg_turnaround_hours?: number, last_30_days: integer, revision_rate: number, trend: list[object]

**ServiceOut** - id: integer, slug: string, name: string, category: string, tagline?: string, description?: string, long_description?: string, turnaround_days: integer, starting_price?: number, icon?: string, form_schema?: list[object], deliverables?: list[string], is_active: boolean, sort_order: integer, pending_count?: integer, total_requests?: integer, prices?: object, price_unit?: string

**ServiceUpdate** - name?: string, category?: string, tagline?: string, description?: string, long_description?: string, turnaround_days?: integer, starting_price?: number, icon?: string, form_schema?: list[], deliverables?: list[], is_active?: boolean, sort_order?: integer

**StatusIn** - status: ref, note?: string

**TicketCreate** - subject: string, message: string, priority?: string, category?: string

**TicketOut** - id: integer, client_id: integer, company_name?: string, subject: string, status: string, priority: string, category?: string, messages?: list[object], created_at?: string, updated_at?: string, resolved_at?: string

**TicketReply** - message: string, status?: string

**TokenOut** - access_token: string, refresh_token: string, token_type?: string, expires_in: integer, user: ref

**UserOut** - id: integer, email: string, full_name: string, role: string, is_active: boolean, avatar_url?: string, phone?: string, timezone?: string, last_login_at?: string, created_at?: string, client?: ref

**ValidationError** - loc: list[object], msg: string, type: string, input?: any, ctx?: object
