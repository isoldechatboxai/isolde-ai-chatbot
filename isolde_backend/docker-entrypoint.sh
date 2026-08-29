#!/bin/sh
set -eu

# A single-container deployment upgrades the schema before Gunicorn accepts
# traffic. Horizontally scaled deployments must run this same command once in
# CI/CD (or a migration Job) and set SKIP_DB_MIGRATE=1 on application pods.
if [ "${SKIP_DB_MIGRATE:-0}" != "1" ]; then
    python -m flask db upgrade
fi

exec "$@"
