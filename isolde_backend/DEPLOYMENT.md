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

## Live validation checklist

Before release, validate real PostgreSQL, Redis, S3, SMTP, Stripe, OAuth, and
AI-provider credentials in staging. Confirm login, provider generation,
storage upload/download, billing webhooks, cancellation, and authenticated
admin calls. This repository does not fabricate those external results.
