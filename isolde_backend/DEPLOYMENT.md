# ISOLDE backend deployment

Run this backend with PostgreSQL, Redis, private S3-compatible storage, HTTPS,
and explicit CORS origins. Copy `.env.example` to an environment-specific
secret store; never commit a real `.env` file.

## Required production configuration

- Set `FLASK_ENV=production` and `FLASK_DEBUG=false`.
- Supply distinct, high-entropy `FLASK_SECRET_KEY` and `JWT_SECRET_KEY`.
- Supply at least one real supported provider credential. Credentials may be
  bootstrapped through environment variables and later rotated through the
  encrypted, masked `/api/admin/v1/providers/settings` contract.
- Use PostgreSQL for `DATABASE_URL`, Redis URLs for rate limiting and
  cancellation, `RAG_STORAGE_BACKEND=database`, and `STORAGE_BACKEND=s3` with
  a private bucket.
- Set a comma-separated allowlist in `CORS_ORIGINS`; never use `*`.
- Set `TRUST_PROXY_HOPS` only to the number of proxies under your control.

`Config.validate()` refuses production startup for SQLite, local storage,
process-local rate limits/cancellation, wildcard CORS, debug mode, placeholder
secrets, or no usable AI provider bootstrap credential.

### Production environment groups

Configure these values in the deployment secret store, not in repository
files:

- **Core (required):** `FLASK_ENV=production`, `FLASK_DEBUG=false`, distinct
  high-entropy `FLASK_SECRET_KEY` and `JWT_SECRET_KEY`, PostgreSQL
  `DATABASE_URL`, explicit HTTPS `CORS_ORIGINS`, and HTTPS `PUBLIC_APP_URL`.
- **AI (required):** at least one supported provider API key and its model
  where the provider requires an explicit model. For example,
  `GEMINI_API_KEY` with `GEMINI_MODEL`, or `OPENAI_API_KEY`; configure a
  supported embedding model/provider before expecting RAG to be available.
- **Redis (required):** `RATELIMIT_STORAGE_URI` and
  `CANCELLATION_REDIS_URL`, each using `redis://` or `rediss://`.
- **Storage (required):** `STORAGE_BACKEND=s3`, `S3_BUCKET`, and the region,
  endpoint, and credentials required by the selected private S3-compatible
  service. Instance-role credentials may be used where the host supports
  them. Keep `RAG_STORAGE_BACKEND=database`.
- **Feature dependent:** `TAVILY_API_KEY` for research; SMTP `MAIL_*` values
  when email verification is enabled (it defaults to enabled in production);
  and the complete client ID, client secret/key material, and HTTPS redirect
  URI group for each enabled OAuth provider. Leave every field in a disabled
  OAuth provider group blank.

## First Render deployment

This repository does not contain a Render Blueprint. Create a Docker web
service manually with repository root directory `isolde_backend`; Render will
use `Dockerfile` and its entrypoint. Provision PostgreSQL, Redis, and private
S3-compatible storage first, then add the production environment groups above
in Render's secret environment settings. Set `TRUST_PROXY_HOPS=1` for Render's
single trusted edge proxy and configure the service health-check path as
`/api/ready`.

For the first single-instance rollout, leave `SKIP_DB_MIGRATE` unset so the
entrypoint runs `python -m flask db upgrade` before Gunicorn. Do not scale past
one instance until that migration completes and `/api/ready` returns HTTP 200.
For subsequent multi-instance rollouts, run the migration exactly once as a
pre-deploy job and set `SKIP_DB_MIGRATE=1` on application instances.

## Migrations and rollout

The image entrypoint executes `python -m flask db upgrade` before Gunicorn for
a single-container deployment. For multiple replicas, run that exact command
once as a CI/CD migration step or Kubernetes Job, confirm `/api/ready`, then
start application replicas with `SKIP_DB_MIGRATE=1`. Do not run concurrent
migration jobs.

For an entirely empty database, the migration path is preferred. The guarded
`flask db-bootstrap` command is available only for an empty, unversioned
database and refuses existing non-empty databases.

## Health and shutdown

Use `/api/live` for process liveness and `/api/ready` for dependency readiness.
Gunicorn receives `SIGTERM` during rollout and is configured with a bounded
graceful timeout; stop routing traffic before terminating old instances.

## Isolated demo/staging Super Admin

This is opt-in and provisions a normal Super Admin account for the separate
Admin Panel to use through `/api/admin/login`; there is no test-login endpoint.
Set these values through the demo/staging secret store only:

- `FLASK_ENV=demo` or `FLASK_ENV=staging`
- `DEMO_ADMIN_BOOTSTRAP_ENABLED=true`
- `DEMO_ADMIN_EMAIL` and a unique high-entropy `DEMO_ADMIN_PASSWORD` (minimum
  16 characters)
- `DEMO_DATABASE_MARKER`, contained in the isolated `DATABASE_URL`
- `DEMO_STORAGE_MARKER`, contained in the isolated private `S3_BUCKET`

Run `python -m flask provision-demo-admin` once after migrations. It never
prints credentials, is idempotent for an existing Super Admin, and refuses a
non-Super-Admin account sharing the configured email. Production startup
rejects the bootstrap setting. Disable it immediately after provisioning by
removing the bootstrap variables or setting the flag to `false`; remove the
account through the normal authenticated admin user-management API if it is no
longer needed.

For a local isolated demo/staging run, inject the values above, then run:

```sh
python -m flask db upgrade
python -m flask provision-demo-admin
gunicorn --bind 0.0.0.0:5000 run:app
```

Sign in through `POST /api/admin/login`, use the returned normal JWT for
`/api/admin/v1/capabilities` and `/api/admin/v1/session`, and revoke the
current session with `DELETE /api/admin/v1/session` when testing is complete.

## Live validation checklist

Before release, validate real PostgreSQL, Redis, S3, SMTP, Stripe, OAuth, and
AI-provider credentials in staging. Confirm login, provider generation,
storage upload/download, billing webhooks, cancellation, and authenticated
admin calls. This repository does not fabricate those external results.

## External production E2E verification

After deployment, provide smoke-test values through the invoking shell or CI
secret store; never add them to a committed `.env` file. The account must be
active, verified, and have enough AI credits. Then run:

```powershell
$env:RUN_EXTERNAL_E2E = "1"
$env:ISOLDE_E2E_BASE_URL = "https://your-deployment.example"
$env:ISOLDE_E2E_EMAIL = "e2e-account@example.com"
$env:ISOLDE_E2E_PASSWORD = "from-secret-store"
python -m pytest test/test_external_e2e.py -q
```

The harness verifies liveness, readiness, matching capability contracts,
password authentication, real non-streaming and streaming provider execution,
RAG querying, optional research with validated citations, and logout. Set
`ISOLDE_E2E_UPLOAD_FILE` to a safe disposable PDF, DOCX, TXT, CSV, or XLSX file
to include the real upload/indexing path. It never prints tokens, passwords,
API keys, or response bodies on failure.
