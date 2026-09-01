# ISOLDE Admin API v1

The Admin Panel is a separate client. It connects to this backend over HTTPS and never reads the database or backend filesystem directly.

## Authentication and errors

Call `POST /api/admin/login`, then send the returned JWT as `Authorization: Bearer <token>`. All `/api/admin/v1/*` endpoints require an active `Admin` or `Super Admin` account. JSON errors use `{"status":"error","message":"..."}` with an appropriate HTTP status.

Configure the separate Admin Panel origin through `CORS_ORIGINS`; never use `*` in production. Do not place secrets in frontend configuration.

## Control-plane endpoints

- `GET /api/admin/v1/capabilities` — supported, unavailable, and unsupported controls.
- `GET|POST /api/admin/v1/api-keys` — Super-Admin-only `isk_` key metadata and issuance. The raw key is returned once only by `POST`.
- `POST /api/admin/v1/api-keys/<key_id>/revoke` — Super-Admin-only, idempotent key revocation.
- `GET /api/admin/v1/dashboard`, `/users`, `/organizations`, `/projects`, and `/conversations` — safe operational and ownership summaries.
- `GET /api/admin/v1/billing/summary`, `/billing/subscriptions`, `/providers/status`, and `/operations` — provider, billing, RAG/storage, rate-limit, and health summaries.
- `PATCH /api/admin/v1/users/{id}` and `/organizations/{id}`; `PATCH /api/admin/v1/organizations/{id}/policy` — validated account and tenant policy changes.
- `GET|PATCH /api/admin/v1/configuration` — validated feature flags and safe branding text.
- `GET|PATCH /api/admin/v1/providers/configuration` — effective active provider and model selections. It never returns API keys.
- `GET|POST|DELETE /api/admin/v1/providers/settings` — masked provider-setting status and validated encrypted secret rotation; plaintext values are never returned.
- `GET /api/admin/v1/audit` — up to 200 recent database-backed administrative events.
- `GET|DELETE /api/admin/v1/session` — current-admin session metadata and secure self-revocation; JWTs and hashes are never returned.
- `GET /api/admin/v1/billing/ledger`, `/billing/events`, and `/billing/invoices`; `POST /billing/invoices/{id}/refund` — paginated, server-authoritative finance visibility and idempotent refund control.
- `GET /api/admin/v1/rag/documents` and `/rag/documents/{id}` — metadata/index inspection only; no chunk text, filesystem paths, or object keys.
- `GET /api/admin/v1/workflows`; `GET|PATCH|DELETE /api/admin/v1/workflows/{id}` — workflow status and audited administration. Execution remains `NOT_SUPPORTED`.
- `GET /api/admin/v1/release` — API, application, and migration version metadata.
- `GET /api/admin/v1/projects` — project ownership, state, and organization-share metadata; never document contents.
- `GET /api/admin/v1/organizations/{id}` — owner, member-role, policy, and shared-project summary.
- `GET /api/admin/v1/users/{id}/sessions` — safe session metadata without IP/user-agent hashes.
- `POST /api/admin/v1/users/{id}/sessions/revoke-all` — revoke another user's active sessions.

Existing authenticated `/api/admin/*` endpoints remain supported for compatibility. New clients should use the versioned contracts above.

All list endpoints that return operational or customer records use bounded `page` and `page_size` parameters (`page_size` is 1–200). Supported list filters are documented by each endpoint response and are validated server-side.

## Runtime product configuration

`GET /api/product/config` is the public, read-only customer configuration contract. It returns only:

- known feature-visibility flags;
- validated plain-text branding fields;
- bundled branding asset references and their capability state.

It never returns provider credentials, OAuth configuration, billing secrets, JWT/session settings, SMTP credentials, private storage configuration, or encryption keys.

Branding asset upload is currently `NOT_CONFIGURED`; bundled assets remain the safe fallback. Image/video providers remain `NOT_CONFIGURED` unless a real implementation is added. Training and browser-triggered deployment are `NOT_SUPPORTED`.

## Deployment contract

Production requires HTTPS, explicit CORS origins, strong Flask/JWT secrets, PostgreSQL, Redis, private S3-compatible storage, SMTP where email flows are enabled, Stripe where billing is enabled, and genuine OAuth/AI-provider credentials. Apply migrations before starting Gunicorn and use `/api/health` and `/api/ready` for rollout verification.
