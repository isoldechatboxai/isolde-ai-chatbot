# ISOLDE Admin API v1

The Admin Panel is a separate client. It connects to this backend over HTTPS and never reads the database or backend filesystem directly.

## Authentication and errors

Call `POST /api/admin/login`, then send the returned JWT as `Authorization: Bearer <token>`. All `/api/admin/v1/*` endpoints require an active `Admin` or `Super Admin` account. JSON errors use `{"status":"error","message":"..."}` with an appropriate HTTP status.

Configure the separate Admin Panel origin through `CORS_ORIGINS`; never use `*` in production. Do not place secrets in frontend configuration.

## Control-plane endpoints

- `GET /api/admin/v1/capabilities` — supported, unavailable, and unsupported controls.
- `GET /api/admin/v1/dashboard`, `/users`, `/organizations`, `/projects`, and `/conversations` — safe operational and ownership summaries.
- `GET /api/admin/v1/billing/summary`, `/billing/subscriptions`, `/providers/status`, and `/operations` — provider, billing, RAG/storage, rate-limit, and health summaries.
- `PATCH /api/admin/v1/users/{id}` and `/organizations/{id}`; `PATCH /api/admin/v1/organizations/{id}/policy` — validated account and tenant policy changes.
- `GET|PATCH /api/admin/v1/configuration` — validated feature flags and safe branding text.
- `GET|PATCH /api/admin/v1/providers/configuration` — effective active provider and model selections. It never returns API keys.
- `GET /api/admin/v1/audit` — up to 200 recent database-backed administrative events.
- `GET /api/admin/v1/release` — API, application, and migration version metadata.
- `GET /api/admin/v1/projects` — project ownership, state, and organization-share metadata; never document contents.
- `GET /api/admin/v1/organizations/{id}` — owner, member-role, policy, and shared-project summary.
- `GET /api/admin/v1/users/{id}/sessions` — safe session metadata without IP/user-agent hashes.
- `POST /api/admin/v1/users/{id}/sessions/revoke-all` — revoke another user's active sessions.

Existing authenticated `/api/admin/*` endpoints remain supported for compatibility. New clients should use the versioned contracts above.

## Runtime product configuration

`GET /api/product/config` is the public, read-only customer configuration contract. It returns only:

- known feature-visibility flags;
- validated plain-text branding fields;
- bundled branding asset references and their capability state.

It never returns provider credentials, OAuth configuration, billing secrets, JWT/session settings, SMTP credentials, private storage configuration, or encryption keys.

Branding asset upload is currently `NOT_CONFIGURED`; bundled assets remain the safe fallback. Image/video providers remain `NOT_CONFIGURED` unless a real implementation is added. Training and browser-triggered deployment are `NOT_SUPPORTED`.

## Deployment contract

Production requires HTTPS, explicit CORS origins, strong Flask/JWT secrets, PostgreSQL, Redis, private S3-compatible storage, SMTP where email flows are enabled, Stripe where billing is enabled, and genuine OAuth/AI-provider credentials. Apply migrations before starting Gunicorn and use `/api/health` and `/api/ready` for rollout verification.
