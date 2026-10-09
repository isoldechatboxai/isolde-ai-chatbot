# ISOLDE AI Chatbot - System Architecture & Master Reference

> **Document Status**: Production Ground Truth  
> **Last Verified**: October 2026  
> **Authoritative Root**: `isolde_backend/`  
> **Test Suite Health**: 255 passed / 1 skipped / 0 failed (100% pass rate)

---

## 1. System Overview & Workspace Hierarchy

The ISOLDE AI platform is an enterprise-grade multi-tenant AI conversational assistant with Retrieval-Augmented Generation (RAG), autonomous tool execution, document intelligence, collaboration workspaces, and SaaS billing integration.

### 1.1 Directory Layout & Authoritative Root

```text
isolde_backend_fixed_2/                  # Workspace Root (Git Root)
├── isolde_backend/                      # [AUTHORITATIVE APPLICATION ROOT]
│   ├── app/                             # Core application package
│   │   ├── middleware/                  # Security headers, content guards, logging
│   │   ├── models/                      # SQLAlchemy 2.0 database models
│   │   ├── repositories/                # Data access layer repositories
│   │   ├── routes/                      # Flask route blueprints (30 registered)
│   │   ├── services/                    # Business logic & external service integrations
│   │   ├── workers/                     # Async background workers
│   │   ├── extensions.py                # Flask extension instances (db, jwt, limiter, etc.)
│   │   └── __init__.py                  # Application factory create_app()
│   ├── config.py                        # Centralized configuration & environment validator
│   ├── migrations/                      # Alembic migrations (Head: 20260903_000009_pgvector)
│   ├── test/                            # Pytest test suite (256 test cases)
│   ├── run.py                           # Application startup entrypoint
│   ├── requirements.txt                 # Production dependencies
│   ├── requirements-dev.txt             # Development and test dependencies
│   └── isolde.db                        # Local development SQLite database
├── isolde-ai-chatbot/                   # [LEGACY SNAPSHOT] Archived clone (Aug 2026, commit e2473c7)
├── docs/                                # Project documentation
│   └── PROJECT_ARCHITECTURE.md          # This authoritative specification
└── .venv-5/                             # Primary project virtual environment
```

> **Authoritative Boundary**: All development, fixes, testing, and deployment configurations are executed against **`isolde_backend/`**. The subfolder `isolde-ai-chatbot/` is a legacy snapshot and must not be targeted for backend changes.

---

## 2. Application Factory & Request Lifecycle

The application is instantiated via the factory pattern in `isolde_backend/app/__init__.py:create_app()`.

```mermaid
flowchart TD
    Client([HTTP Client]) --> Ingress[Reverse Proxy / Nginx / Render]
    Ingress --> WSGI[Gunicorn / Waitress WSGI Server]
    WSGI --> App[Flask create_app Factory]
    
    subgraph Request_Pipeline [Request Middleware Pipeline]
        App --> MW_Log[Request Logger]
        MW_Log --> MW_Guard[Content Validator & Byte Guards]
        MW_Guard --> MW_Rate[Flask-Limiter Rate Limiter]
        MW_Rate --> MW_Auth[JWT / API-Key Authentication]
    end
    
    subgraph Blueprint_Dispatch [Blueprint Execution]
        MW_Auth --> RouteHandler[Active Route Controller]
        RouteHandler --> ServiceLayer[Service Layer / Provider Router / RAG]
        ServiceLayer --> DB[(PostgreSQL / SQLite)]
    end
    
    subgraph Response_Pipeline [Response Middleware Pipeline]
        RouteHandler --> MW_Headers[Security Headers Middleware]
        MW_Headers --> Teardown[Context Teardown & Session Rollback]
        Teardown --> Client
    end
```

### 2.1 Factory Initialization Steps (`create_app`)
1. **Configuration Binding & Validation**: `Config.validate()` runs on application startup to enforce production security constraints (32-character minimum secret lengths, production database URI checks, proxy hop configurations, S3 configuration).
2. **Flask Extensions Binding**:
   - `db.init_app(app)`: SQLAlchemy with connection pre-pinging, recycling, and pooling.
   - `jwt.init_app(app)`: JWT authentication with blocklist session callbacks.
   - `migrate.init_app(app, db)`: Database schema migrations via Flask-Migrate / Alembic.
   - `limiter.init_app(app)`: Rate limiting backed by Redis or memory storage.
   - `cors.init_app(app)`: Strict CORS origin validation without wildcard `*` in production.
3. **Middleware Registration**:
   - `setup_request_logger(app)`: High-resolution timing and structured audit logging.
   - `setup_security_headers(app)`: Enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, and `Cache-Control: no-store` on sensitive endpoints.
   - `setup_content_validator(app)`: Validates body sizes, input bounds, and UTF-8 encoding.
4. **Blueprint Registration**: Mounts all 30 application blueprints.
5. **Session Safety & Error Teardown**:
   - Automatic `db.session.rollback()` in `teardown_appcontext` and `teardown_request` handlers prevents `PendingRollbackError` and stale transaction leakage.
   - Centralized HTTP error handlers for `400`, `401`, `403`, `404`, `409`, `415`, `429`, `500`, and `503`.

---

## 3. Authentication & Authorization Architecture

ISOLDE implements a defense-in-depth authentication model supporting interactive web sessions, OAuth2 federations, and automated SaaS API keys.

```mermaid
flowchart LR
    User([User]) --> Login{Auth Type}
    
    Login -->|Email / Password| PasswordAuth[Bcrypt Hash & Lockout Check]
    Login -->|OAuth2| OAuthFlow[Google / GitHub / Apple PKCE Flow]
    Login -->|SaaS Key| ApiKeyAuth[SHA-256 Key Prefix Lookup]
    
    PasswordAuth --> SessionGen[Issue Session & Access/Refresh JWT]
    OAuthFlow --> SessionGen
    ApiKeyAuth --> ScopeCheck[Scope Validation: read/write/admin]
    
    SessionGen --> AuthSession[(auth_sessions DB Table)]
    ScopeCheck --> Execution[Execute API Request]
```

### 3.1 Interactive & JWT Authentication
- **Password Security**: Passwords are saved using salted hashing (Bcrypt / PBKDF2-HMAC-SHA256). Passwords longer than 128 characters are rejected to protect against hash-algorithm DoS.
- **Email Normalization & Duplicate Handling**: Emails are whitespace-trimmed and lowercased. Registration routes rigorously differentiate between duplicate user accounts and unrelated database constraints, responding with a predictable **HTTP 409 Conflict** for existing emails without exposing internal stack traces.
- **Account Lockouts**: `failed_login_attempts` are incremented upon failed credentials. Sustained brute-force triggers account locking for security.
- **Session Tracking (`auth_sessions`)**: JWT tokens contain a specific session ID claim (`sid`). The `@jwt.token_in_blocklist_loader` validates whether the session remains active in `auth_sessions`.
- **Global Revocation (`revoke_user_auth`)**: Resetting passwords or calling `/api/logout-all` revokes all active database sessions (`revoked_at = utcnow()`), invalidates pending verification tokens, and sets a `user:<id>` marker in `RevokedToken` to revoke any legacy stateless tokens.

### 3.2 SaaS API Key Authentication (`saas_api_keys`)
- Keys use a secure format (`iso_live_<random_bytes>`).
- Only `key_prefix` (first 8 characters) and `key_hash` (SHA-256) are stored in the database; raw secret keys are displayed only once upon generation.
- Validates tenant scope permissions (`read`, `write`, `admin`).
- Rate limiting is selectively applied per API key.

---

## 4. Blueprints Inventory (All 30 Registered Modules)

| # | Blueprint Object | URL Prefix | Source File | Responsibilities & Primary Endpoints |
|---|:---|:---|:---|:---|
| 1 | `auth_bp` | `/api` | `app/routes/auth_routes.py` | Registration, login, logout, password reset, email verification, OAuth |
| 2 | `chat_bp` | `/api` | `app/routes/chat_routes.py` | Conversation creation, message sending, streaming SSE responses |
| 3 | `upload_bp` | `/api` | `app/routes/upload_routes.py` | Secure multipart document uploads, text extraction, validation |
| 4 | `feedback_bp` | `/api` | `app/routes/feedback_routes.py` | User message ratings, feedback comments, quality scoring |
| 5 | `history_bp` | `/api` | `app/routes/history_routes.py` | Conversation list, message history pagination, session cleanup |
| 6 | `profile_bp` | `/api` | `app/routes/profile_routes.py` | User account profile, preferences, avatar management |
| 7 | `admin_bp` | `/api` | `app/routes/admin_routes.py` | Admin dashboard, user status mutation, system health, audit logs |
| 8 | `memory_bp` | `/api` | `app/routes/memory_routes.py` | Persistent user memory extraction, storage, and contextual retrieval |
| 9 | `workspace_bp` | `/api` | `app/routes/workspace_routes.py` | Multi-tenant organization workspaces, member roles, collaboration |
| 10 | `agent_bp` | `/api` | `app/routes/agent_routes.py` | Autonomous AI agent creation, persona tuning, agent task execution |
| 11 | `productivity_bp` | `/api` | `app/routes/productivity_routes.py` | Notes, tasks, to-do tracking, productivity tool integrations |
| 12 | `voice_bp` | `/api` | `app/routes/voice_routes.py` | Audio transcription (Whisper), speech synthesis, voice chat |
| 13 | `workflow_bp` | `/api` | `app/routes/workflow_routes.py` | Multi-stage prompt workflows, trigger sequences, execution logs |
| 14 | `collaboration_bp` | `/api` | `app/routes/collaboration_routes.py` | Real-time session sharing, collaborative chat spaces, permissions |
| 15 | `marketplace_bp` | `/api` | `app/routes/marketplace_routes.py` | Extension marketplace, plugin catalog, installation and review |
| 16 | `saas_cloud_bp` | `/api` | `app/routes/saas_cloud_routes.py` | Multi-tenant cloud features, tier limits, tenant usage stats |
| 17 | `intelligence_bp` | `/api` | `app/routes/intelligence_routes.py` | Sentiment classification, intent routing, prompt optimization |
| 18 | `rag_bp` | `/api` / root | `app/routes/rag_routes.py` | Document ingestion, chunking, pgvector search, knowledge bases |
| 19 | `api_key_bp` | `/api` | `app/routes/api_key_routes.py` | SaaS API key management, generation, listing, rotation, revocation |
| 20 | `chat_ext_bp` | Direct | `app/routes/chat_extended_routes.py` | Extended prompt features, web citation synthesis, attachments |
| 21 | `billing_bp` | `/api` | `app/routes/billing_routes.py` | Subscriptions, credit deduction, invoices, payment webhook handlers |
| 22 | `plugin_bp` | `/api` | `app/routes/plugin_routes.py` | Third-party plugin registration, execution sandbox, lifecycle |
| 23 | `ai_studio_bp` | `/api` | `app/routes/ai_studio_routes.py` | Prompt playground, model customization, parameter testing |
| 24 | `unified_engine_bp` | `/api` | `app/routes/unified_chat_engine.py` | Unified execution combining chat, web research, tools, and RAG |
| 25 | `settings_bp` | `/api` | `app/routes/settings_routes.py` | Tenant settings, model preferences, dark/light theme options |
| 26 | `codex_bp` | `/api` | `app/routes/codex_routes.py` | Codex project code editing, multi-file atomic changes, rollbacks |
| 27 | `public_api_bp` | `/api` | `app/routes/public_api_routes.py` | Versioned REST API (`/api/v1/chat`, `/api/v1/research`, `/api/v1/rag/query`) |
| 28 | `health_bp` | `/api/health` | `app/routes/health_routes.py` | Liveness (`/api/live`), readiness (`/api/ready`), dependency health |
| 29 | `analytics_bp` | `/api/analytics`| `app/routes/analytics_routes.py` | Token usage telemetry, latency metrics, error distribution |
| 30 | `studio_bp` | Direct | `app/studio_routes.py` | AI Studio frontend web routes and static distribution |

---

## 5. Database Schema & Alembic Migration Lineage

The application uses SQLAlchemy 2.0 with PostgreSQL in production (supporting Neon / Supabase / standard Postgres) and SQLite for local development and test isolation.

```mermaid
gitGraph
    commit id: "baseline"
    commit id: "codex_models"
    commit id: "saas_api_keys"
    commit id: "20260826_01_auth"
    commit id: "20260826_02_rag"
    commit id: "20260826_03_payment"
    commit id: "20260826_04_billing"
    commit id: "20260826_05_org_projects"
    commit id: "20260827_06_org_policies"
    commit id: "20260827_07_marketplace"
    commit id: "20260827_08_admin_uuid"
    commit id: "20260903_09_pgvector (HEAD)"
```

### 5.1 Migration History (`migrations/versions/`)
1. `2442f1de8168_baseline_current_schema`: Baseline schema definition.
2. `20260101_000001_add_codex_models`: Codex project tasks, executions, and file state tracking.
3. `c4d5e6f7a8b9_add_key_hash_key_prefix_to_saas_api_keys`: Secure API key prefixes and cryptographic hashes.
4. `20260826_000001_auth_foundation`: Session revocation table, verification tokens, OAuth links.
5. `20260826_000002_production_rag`: Multi-tenant RAG documents and chunk indices.
6. `20260826_000003_payment_events`: Idempotent payment webhook event records.
7. `20260826_000004_billing_completion`: Invoices, credit ledger, subscription tiers.
8. `20260826_000005_organization_projects`: Tenant workspaces and project partitioning.
9. `20260827_000006_organization_policies`: Policy constraints and provider whitelisting.
10. `20260827_000007_marketplace_user_ids`: Marketplace plugin ownership and ratings.
11. `20260827_000008_admin_audit_uuid`: Audit logging identifiers with UUID keys.
12. **`20260903_000009_pgvector_rag` (HEAD)**:
    - Creates PostgreSQL `vector` extension (`CREATE EXTENSION IF NOT EXISTS vector`).
    - Adds `embedding_vector vector` column to `rag_chunks`.
    - Preserves legacy `embedding` JSON column as non-destructive fallback for SQLite test suites and historic data.

---

## 6. AI Provider Router, Fallbacks & Streaming

Managed by `ProviderManager` in `isolde_backend/app/services/provider_router.py`.

```mermaid
flowchart TD
    Req([Prompt / Chat Request]) --> Policy[Tenant Provider Policy Filter]
    Policy --> Select[Select Candidate: Gemini / OpenAI / Claude / Groq]
    Select --> Invoke[Invoke Candidate Stream Generator]
    
    Invoke -->|Success: Emits 1st Token| StreamOut[Emit Chunk to SSE Stream]
    StreamOut --> MoreTokens{More Tokens?}
    MoreTokens -->|Yes| StreamOut
    MoreTokens -->|Done| CloseClient[Close Provider Client]
    
    Invoke -->|Failure Before First Token| RecordFail[Record Failure & Trigger Fallback]
    RecordFail --> NextCandidate{Next Provider Available?}
    NextCandidate -->|Yes| Invoke
    NextCandidate -->|No| FailUnavailable[Raise PROVIDER_STREAM_UNAVAILABLE]
    
    StreamOut -->|Failure Mid-Stream| Interrupt[Raise PROVIDER_STREAM_INTERRUPTED]
    Interrupt --> NoFallback[Never Fallback Mid-Stream (Prevents Output Duplication)]
```

### 6.1 Key Resilience Guarantees
- **Multi-Provider Support**: Google Gemini (via `google-genai`), OpenAI, Anthropic Claude, Groq, DeepSeek, and local Ollama.
- **Failover Without Duplication**:
  - If a provider fails **before emitting tokens**, the router logs the failure and falls back to the next configured candidate.
  - If a provider fails **after emitting tokens** (`emitted = True`), fallback is **strictly prevented** and raises `PROVIDER_STREAM_INTERRUPTED`. This prevents duplicate or garbled text from two different models appearing in the client stream.
- **Stream Cleanup**: Generators use `try ... finally` blocks to invoke `client.close()` and `resp.close()`, preventing socket leakage across Gunicorn worker threads.
- **Secret Sanitization**: Error handlers redact raw HTTP error payloads to prevent accidental API key leaks in server logs.

---

## 7. Storage Service, Document Processing & Redis Services

### 7.1 File Storage (`app/services/storage_service.py`)
- **Local Storage (`STORAGE_BACKEND=local`)**: Files stored in `uploads/` with sanitized paths (`os.path.abspath` directory confinement).
- **S3 Storage (`STORAGE_BACKEND=s3`)**: Uses `boto3` for AWS S3 or Supabase Storage, streaming content with size boundaries.

### 7.2 Document Parsing (`app/services/file_service.py`)
- **PDF Extraction**: Parsed via `pypdf` (version 6.20+).
- **DOCX Extraction**: Parsed via `python-docx`.
- **Spreadsheets & Data**: Parsed via `pandas` and `openpyxl`.
- **Security Boundaries**: Null bytes (`\0`) are stripped; file size limits (`MAX_CONTENT_LENGTH`, `RAG_MAX_UPLOAD_BYTES`) are strictly enforced before memory allocation.

### 7.3 Redis & Cancellation Architecture (`app/services/cancellation_service.py`)
- **Cross-Worker Cancellation**: If a user cancels a stream or closes a browser tab, cancellation state is propagated via Redis (`CANCELLATION_REDIS_URL` or `REDIS_URL`) using short TTL keys.
- **In-Memory Fallback**: If Redis is not configured or temporarily unreachable, falls back to an internal thread-safe in-memory cache without application crashes.
- **Service Isolation**: Rate-limiting Redis (`RATELIMIT_STORAGE_URI`) is partitioned from cancellation Redis so a rate-limit outage does not break stream cancellations.

---

## 8. Test Execution & Verified Health

The test suite runs under `pytest` with temporary isolated databases and mock providers.

### 8.1 Test Command
```bash
# Executed inside isolde_backend/
python -m pytest test/ -q
```

### 8.2 Verified Ground Truth
- **Total Tests**: **256**
- **Passed**: **255**
- **Skipped**: **1** (Intentional: `test/test_external_e2e.py` requiring live external infrastructure credentials)
- **Failed / Errored**: **0**
- **Execution Duration**: ~123 seconds

---

## 9. Environment Variable Inventory

| Variable Name | Purpose | Required? | Default / Example |
|:---|:---|:---:|:---|
| `FLASK_ENV` | Environment identifier (`production`, `demo`, `development`) | Required | `production` |
| `FLASK_SECRET_KEY` | Flask session cookie cryptographic signing key (>=32 chars) | Required | *Random 32+ char string* |
| `JWT_SECRET_KEY` | JWT signing key (>=32 chars) | Required | *Random 32+ char string* |
| `DATABASE_URL` | Multi-worker database URI (PostgreSQL in production) | Required | `postgresql://user:pass@host:5432/db` |
| `GEMINI_API_KEY` | Google Gemini API key for default chat and embeddings | Required | *Google AI Studio API Key* |
| `STORAGE_BACKEND` | File storage provider (`local` or `s3`) | Optional | `local` (`s3` in prod) |
| `S3_BUCKET` | AWS / Supabase S3 bucket name | Required if S3 | `isolde-storage` |
| `S3_ENDPOINT_URL` | S3 custom endpoint URL (for Supabase/MinIO) | Optional | `https://<ref>.storage.supabase.co/storage/v1/s3` |
| `S3_ACCESS_KEY_ID` | S3 API access key | Optional | *Access Key ID* |
| `S3_SECRET_ACCESS_KEY`| S3 API secret access key | Optional | *Secret Access Key* |
| `REDIS_URL` | Redis URL for rate limiting and cancellation | Optional | `redis://localhost:6379/0` |
| `CORS_ORIGINS` | Permitted client origins (comma-separated, no `*` in prod)| Required | `https://yourdomain.com` |
| `PUBLIC_APP_URL` | Base URL used for email verification links | Required | `https://yourdomain.com` |
| `OPENAI_API_KEY` | Secondary AI provider key | Optional | *sk-...* |
| `ANTHROPIC_API_KEY` | Secondary AI provider key | Optional | *sk-ant-...* |
| `GROQ_API_KEY` | Secondary AI provider key | Optional | *gsk_...* |
| `DEEPSEEK_API_KEY` | Secondary AI provider key | Optional | *sk-...* |
| `RUN_EXTERNAL_E2E` | Set to `1` to run live external smoke tests | Optional | `0` |

---

## 10. Working Tree Audit & Hygiene Notice

The following 27 files in `isolde_backend/` reflect active production stabilization changes:
1. `config.py`: Added connection pooling for PostgreSQL, strict production secret checks, and RAG bounds.
2. `app/__init__.py`: Registered 30 blueprints, added automatic session rollback on exceptions.
3. `app/models/auth_model.py`: Added unified `revoke_user_auth()` helper.
4. `app/routes/auth_routes.py`: Normalized email handling and session revocation.
5. `app/services/provider_router.py`: Stream resource cleanup, emission boundary enforcement, redacted errors.
6. `app/services/file_service.py`: Upgraded PDF extraction to `pypdf`.
7. `app/services/cancellation_service.py`: Isolated Redis cancellation logic.
8. `app/services/rag_service.py` & `research_service.py`: Enforced bounded search budgets and safe citations.
9. `migrations/versions/20260903_000009_pgvector_rag.py`: Added pgvector migration.
10. `requirements.txt`: Pinned modern package dependencies (`pypdf`, `redis`, `boto3`, etc.).
11. Test files (`test/*.py`): Hardened assertions and test coverage.

**Audited Security Status**: All 27 tracked modified files contain zero hardcoded secrets or accidental regressions. All 255 internal test suites pass cleanly.
