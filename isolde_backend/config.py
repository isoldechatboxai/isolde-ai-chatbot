import os
import re
from datetime import timedelta
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be a valid integer."
        ) from exc


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be a valid number."
        ) from exc


def _env_list(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def _normalize_database_url(database_url: str) -> str:
    """
    Normalize DATABASE_URL values commonly supplied by hosting platforms.
    PostgreSQL URLs may be supplied as postgres://... while SQLAlchemy
    expects postgresql://...
    """
    if database_url.startswith("postgres://"):
        return "postgresql://" + database_url[len("postgres://"):]
    return database_url


def _database_engine_options(database_url: str) -> dict:
    """Return conservative pool settings only for networked PostgreSQL.

    Managed PostgreSQL services can close an idle TLS connection while it is
    still present in a worker pool. ``pool_pre_ping`` discards that stale
    connection before a request starts; ``pool_recycle`` limits its age.
    Neither setting retries an application write or changes TLS verification.
    """
    if not database_url.startswith(("postgresql://", "postgres://")):
        return {}
    return {
        "pool_pre_ping": True,
        "pool_recycle": _env_int("DB_POOL_RECYCLE_SECONDS", 1800),
        "pool_size": _env_int("DB_POOL_SIZE", 5),
        "max_overflow": _env_int("DB_POOL_MAX_OVERFLOW", 5),
        "pool_timeout": _env_int("DB_POOL_TIMEOUT_SECONDS", 30),
    }


class Config:
    # ==========================================================
    # Environment
    # ==========================================================
    ENVIRONMENT = os.getenv(
        "FLASK_ENV",
        os.getenv("ENVIRONMENT", "development"),
    ).strip().lower()

    IS_PRODUCTION = ENVIRONMENT in {
        "production",
        "prod",
    }
    IS_DEMO_STAGING = ENVIRONMENT in {"demo", "staging"}
    DEMO_ADMIN_BOOTSTRAP_ENABLED = _env_bool("DEMO_ADMIN_BOOTSTRAP_ENABLED")
    DEMO_ADMIN_EMAIL = os.getenv("DEMO_ADMIN_EMAIL", "").strip().lower()
    DEMO_ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "")
    # Explicit markers make a copied demo configuration fail before it can
    # target a production database or object bucket by mistake.
    DEMO_DATABASE_MARKER = os.getenv("DEMO_DATABASE_MARKER", "").strip().lower()
    DEMO_STORAGE_MARKER = os.getenv("DEMO_STORAGE_MARKER", "").strip().lower()

    # ==========================================================
    # Flask Core
    # ==========================================================
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip()

    DEBUG = _env_bool(
        "FLASK_DEBUG",
        default=False,
    )

    TESTING = _env_bool(
        "FLASK_TESTING",
        default=False,
    )

    # ==========================================================
    # Database
    # ==========================================================
    _database_url = os.getenv("DATABASE_URL", "").strip()
    if _database_url:
        SQLALCHEMY_DATABASE_URI = _normalize_database_url(
            _database_url
        )
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"sqlite:///{os.path.join(BASE_DIR, 'isolde.db')}"
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Keep managed PostgreSQL connections healthy across long-lived Gunicorn
    # workers. Local/test engines keep their existing default behavior.
    SQLALCHEMY_ENGINE_OPTIONS = _database_engine_options(SQLALCHEMY_DATABASE_URI)

    # Avoid leaking SQL queries in production logs.
    SQLALCHEMY_ECHO = _env_bool(
        "SQLALCHEMY_ECHO",
        default=False,
    )

    # ==========================================================
    # JWT
    # ==========================================================
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()

    # Unit 2B / Part 1 / Part 3 hardening:
    # JWT algorithms and transport must be explicit.
    JWT_ALGORITHM = "HS256"
    JWT_DECODE_ALGORITHMS = ["HS256"]
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
    JWT_IDENTITY_CLAIM = "sub"

    # Keep JWT error responses consistent with existing handlers.
    JWT_ERROR_MESSAGE_KEY = "error"

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=_env_int(
            "JWT_ACCESS_TOKEN_EXPIRES_MIN",
            60,
        )
    )

    REQUIRE_EMAIL_VERIFICATION = _env_bool(
        "REQUIRE_EMAIL_VERIFICATION", default=IS_PRODUCTION
    )
    EMAIL_VERIFICATION_TOKEN_MINUTES = _env_int("EMAIL_VERIFICATION_TOKEN_MINUTES", 1440)
    PASSWORD_RESET_TOKEN_MINUTES = _env_int("PASSWORD_RESET_TOKEN_MINUTES", 15)
    EXPOSE_TEST_AUTH_TOKENS = _env_bool("EXPOSE_TEST_AUTH_TOKENS", default=True)

    # OAuth/OIDC authorization-code integrations. Empty values disable the
    # corresponding provider; credentials always remain server-side.
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    GITHUB_OAUTH_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "").strip()
    GITHUB_OAUTH_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "").strip()
    GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "").strip()
    APPLE_OAUTH_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "").strip()
    APPLE_OAUTH_REDIRECT_URI = os.getenv("APPLE_OAUTH_REDIRECT_URI", "").strip()
    APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "").strip()
    APPLE_KEY_ID = os.getenv("APPLE_KEY_ID", "").strip()
    APPLE_PRIVATE_KEY = os.getenv("APPLE_PRIVATE_KEY", "").strip()
    MICROSOFT_OAUTH_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "").strip()
    MICROSOFT_OAUTH_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "").strip()
    MICROSOFT_OAUTH_REDIRECT_URI = os.getenv("MICROSOFT_OAUTH_REDIRECT_URI", "").strip()
    MICROSOFT_OAUTH_TENANT = os.getenv("MICROSOFT_TENANT", "").strip()
    OAUTH_HTTP_TIMEOUT_SECONDS = _env_int("OAUTH_HTTP_TIMEOUT_SECONDS", 10)
    PROVIDER_HTTP_TIMEOUT_SECONDS = _env_int("PROVIDER_HTTP_TIMEOUT_SECONDS", 60)

    # ==========================================================
    # Gemini
    # ==========================================================
    GEMINI_API_KEY = os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()

    GEMINI_MODEL = os.getenv(
        "GEMINI_MODEL",
        "",
    ).strip()

    GEMINI_EMBEDDING_MODEL = os.getenv(
        "GEMINI_EMBEDDING_MODEL",
        "",
    ).strip()
    # Environment-backed provider credentials permit an initial secure
    # production bootstrap before an administrator configures encrypted
    # provider settings in the database. Empty values simply disable a
    # provider; no credentials are ever returned through an API.
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "").strip()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()

    # Optional web research provider.  Empty credentials deliberately leave
    # web research unavailable instead of falling back to an implicit service.
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
    RESEARCH_HTTP_TIMEOUT_SECONDS = _env_int("RESEARCH_HTTP_TIMEOUT_SECONDS", 8)
    RESEARCH_FETCH_MAX_SOURCES = _env_int("RESEARCH_FETCH_MAX_SOURCES", 2)
    RESEARCH_FETCH_MAX_BYTES = _env_int("RESEARCH_FETCH_MAX_BYTES", 200_000)
    RESEARCH_FETCH_MAX_CHARS = _env_int("RESEARCH_FETCH_MAX_CHARS", 12_000)
    RESEARCH_CONTEXT_MAX_CHARS = _env_int("RESEARCH_CONTEXT_MAX_CHARS", 24_000)
    CHAT_MAX_PROMPT_CHARS = _env_int("CHAT_MAX_PROMPT_CHARS", 12_000)
    RESEARCH_QUERY_MAX_CHARS = _env_int("RESEARCH_QUERY_MAX_CHARS", 2_000)
    RAG_QUERY_MAX_CHARS = _env_int("RAG_QUERY_MAX_CHARS", 4_000)

    # ==========================================================
    # Uploads
    # ==========================================================
    UPLOAD_FOLDER = os.path.join(
        BASE_DIR,
        os.getenv(
            "UPLOAD_FOLDER",
            "uploads",
        ).strip(),
    )

    MAX_CONTENT_LENGTH = (
        _env_int(
            "MAX_CONTENT_LENGTH_MB",
            15,
        )
        * 1024
        * 1024
    )
    # RAG uploads are streamed and checked independently of Flask's global
    # Content-Length guard.  This also protects deployments receiving
    # chunked multipart bodies without a trustworthy Content-Length header.
    RAG_MAX_UPLOAD_BYTES = _env_int("RAG_MAX_UPLOAD_BYTES", MAX_CONTENT_LENGTH)

    ALLOWED_EXTENSIONS = {
        "pdf",
        "docx",
        "txt",
        "csv",
        "xlsx",
        "png",
        "jpg",
        "jpeg",
    }

    # ==========================================================
    # CORS
    # ==========================================================
    CORS_ORIGINS = _env_list(
        "CORS_ORIGINS",
        default="*",
    )

    # ==========================================================
    # Vector Store
    # ==========================================================
    VECTOR_STORE_DIR = os.path.join(
        BASE_DIR,
        os.getenv(
            "VECTOR_STORE_DIR",
            "vector_store",
        ).strip(),
    )
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
    S3_REGION = os.getenv("S3_REGION", "").strip()
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "").strip()
    S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip()
    S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
    PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "").strip().lower()
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "").strip()
    STRIPE_PRICE_ENTERPRISE = os.getenv("STRIPE_PRICE_ENTERPRISE", "").strip()
    PAYMENT_SUCCESS_URL = os.getenv("PAYMENT_SUCCESS_URL", "").strip()
    PAYMENT_CANCEL_URL = os.getenv("PAYMENT_CANCEL_URL", "").strip()
    IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "").strip().lower()
    VIDEO_PROVIDER = os.getenv("VIDEO_PROVIDER", "").strip().lower()
    RAG_STORAGE_BACKEND = os.getenv("RAG_STORAGE_BACKEND", "database").strip().lower()
    RAG_RELEVANCE_THRESHOLD = _env_float("RAG_RELEVANCE_THRESHOLD", 0.55)

    # ==========================================================
    # Logging
    # ==========================================================
    LOG_DIR = os.path.join(
        BASE_DIR,
        os.getenv(
            "LOG_DIR",
            "logs",
        ).strip(),
    )
    LOG_TO_FILE = _env_bool("LOG_TO_FILE", default=not IS_PRODUCTION)

    # ==========================================================
    # Security
    # ==========================================================
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv(
        "SESSION_COOKIE_SAMESITE",
        "Lax",
    ).strip()

    # ==========================================================
    # Part 1 / Part 3 rate limits
    # ==========================================================
    AUTH_RATE_LIMIT = os.getenv(
        "AUTH_RATE_LIMIT",
        "10 per minute",
    ).strip()

    API_KEY_RATE_LIMIT = os.getenv(
        "API_KEY_RATE_LIMIT",
        "5 per minute",
    ).strip()

    SAAS_API_KEY_RATE_LIMIT = os.getenv(
        "SAAS_API_KEY_RATE_LIMIT",
        "10 per minute",
    ).strip()
    PERMANENT_SESSION_LIFETIME = timedelta(hours=_env_int("SESSION_LIFETIME_HOURS", 12))
    SESSION_REFRESH_EACH_REQUEST = False
    PREFERRED_URL_SCHEME = "https" if IS_PRODUCTION else "http"
    TRUST_PROXY_HOPS = _env_int("TRUST_PROXY_HOPS", 0)
    RATELIMIT_STORAGE_URI = os.getenv(
        "RATELIMIT_STORAGE_URI", "memory://"
    ).strip()
    CANCELLATION_REDIS_URL = os.getenv("CANCELLATION_REDIS_URL", RATELIMIT_STORAGE_URI if RATELIMIT_STORAGE_URI.startswith("redis") else "").strip()
    CANCELLATION_TTL_SECONDS = _env_int("CANCELLATION_TTL_SECONDS", 900)
    REDIS_CONNECT_TIMEOUT_SECONDS = _env_int("REDIS_CONNECT_TIMEOUT_SECONDS", 2)
    REDIS_SOCKET_TIMEOUT_SECONDS = _env_int("REDIS_SOCKET_TIMEOUT_SECONDS", 2)
    CHAT_RATE_LIMIT = os.getenv("CHAT_RATE_LIMIT", "20 per minute").strip()
    UPLOAD_RATE_LIMIT = os.getenv("UPLOAD_RATE_LIMIT", "10 per minute").strip()
    OAUTH_RATE_LIMIT = os.getenv("OAUTH_RATE_LIMIT", "20 per minute").strip()
    BILLING_RATE_LIMIT = os.getenv("BILLING_RATE_LIMIT", "10 per minute").strip()
    CREDIT_TOKENS_PER_UNIT = _env_int("CREDIT_TOKENS_PER_UNIT", 1000)

    MAIL_SERVER = os.getenv("MAIL_SERVER", "").strip()
    MAIL_PORT = _env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", default=True)
    MAIL_TIMEOUT_SECONDS = _env_int("MAIL_TIMEOUT_SECONDS", 10)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "").strip()
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "").strip()
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "").strip()
    PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://127.0.0.1:5000").strip().rstrip("/")

    # ==========================================================
    # Application Paths
    # ==========================================================
    FRONTEND_INDEX = os.path.join(
        FRONTEND_DIR,
        "index.html",
    )

    # ==========================================================
    # Validation
    # ==========================================================
    @staticmethod
    def _is_placeholder_secret(value: str | None) -> bool:
        """Reject obvious insecure placeholder values without blocking valid secrets."""
        if value is None:
            return True

        cleaned = value.strip()
        if not cleaned:
            return True

        normalized = re.sub(r"[^a-z0-9]", "", cleaned.lower())
        insecure_tokens = {
            "changeme",
            "change_me",
            "replace_me",
            "placeholder",
            "example",
            "examplekey",
            "examplesecret",
            "devsecret",
            "devjwtsecret",
            "devflasksecret",
            "testsecret",
            "yoursecretkey",
            "yourjwtsecret",
            "yourflasksecretkey",
            "yourapikey",
            "yourgeminiapikey",
            "secret",
            "password",
            "passphrase",
            "jwtsecret",
            "flasksecret",
        }
        if normalized in insecure_tokens:
            return True

        lower_value = cleaned.lower()
        if any(token in lower_value for token in (
            "example",
            "placeholder",
            "change_me",
            "change-me",
            "replace_me",
            "replace-me",
            "test-secret",
            "testsecret",
            "dev-secret",
            "devsecret",
            "your-secret",
            "yoursecret",
        )):
            return True

        return False

    @staticmethod
    def _is_valid_public_url(value: str, require_https: bool = False, origin_only: bool = False) -> bool:
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        if parsed.scheme not in ({"https"} if require_https else {"http", "https"}):
            return False
        if not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
            return False
        if origin_only and (parsed.path not in {"", "/"} or parsed.query):
            return False
        return True

    @classmethod
    def validate(cls) -> None:
        """
        Validate required production configuration.

        Development can run without external secrets so that local
        development and repository setup remain possible.
        Production must fail fast when critical configuration is missing.
        """
        if cls.DEMO_ADMIN_BOOTSTRAP_ENABLED:
            if cls.IS_PRODUCTION:
                raise RuntimeError("DEMO_ADMIN_BOOTSTRAP_ENABLED must never be enabled in production.")
            if not cls.IS_DEMO_STAGING:
                raise RuntimeError("Demo admin bootstrap is allowed only when FLASK_ENV is demo or staging.")
            if not cls.DEMO_DATABASE_MARKER or cls.DEMO_DATABASE_MARKER not in cls.SQLALCHEMY_DATABASE_URI.lower():
                raise RuntimeError("DEMO_DATABASE_MARKER must be present in DATABASE_URL when demo bootstrap is enabled.")
            if cls.STORAGE_BACKEND != "s3" or not cls.DEMO_STORAGE_MARKER or cls.DEMO_STORAGE_MARKER not in cls.S3_BUCKET.lower():
                raise RuntimeError("Demo bootstrap requires an isolated S3 bucket matching DEMO_STORAGE_MARKER.")
            if "*" in (cls.CORS_ORIGINS or []):
                raise RuntimeError("CORS_ORIGINS must be explicit when demo bootstrap is enabled.")

        if not cls.IS_PRODUCTION:
            return

        missing = []
        unsafe = []

        for key_name, value in (
            ("FLASK_SECRET_KEY", cls.SECRET_KEY),
            ("JWT_SECRET_KEY", cls.JWT_SECRET_KEY),
        ):
            if not value or not value.strip():
                missing.append(key_name)
                continue
            if cls._is_placeholder_secret(value):
                unsafe.append(key_name)

        if missing:
            raise RuntimeError(
                "Missing required production environment variables: "
                + ", ".join(missing)
            )

        if cls.DEBUG:
            raise RuntimeError(
                "FLASK_DEBUG must be disabled in production."
            )

        cors_origins = cls.CORS_ORIGINS or []
        if "*" in cors_origins or any(origin.strip() == "*" for origin in cors_origins):
            raise RuntimeError(
                "CORS_ORIGINS must not use '*' in production."
            )
        if not cors_origins or any(
            not cls._is_valid_public_url(origin, require_https=True, origin_only=True)
            for origin in cors_origins
        ):
            raise RuntimeError("CORS_ORIGINS must contain only explicit HTTPS origins in production.")

        if unsafe:
            raise RuntimeError(
                "Production secrets must not use empty or insecure placeholder values: "
                + ", ".join(unsafe)
            )

        if not cls._is_valid_public_url(cls.PUBLIC_APP_URL, require_https=True):
            raise RuntimeError("PUBLIC_APP_URL must be an absolute HTTPS URL in production.")

        oauth_groups = {
            "Google": (
                ("GOOGLE_OAUTH_CLIENT_ID", cls.GOOGLE_OAUTH_CLIENT_ID),
                ("GOOGLE_OAUTH_CLIENT_SECRET", cls.GOOGLE_OAUTH_CLIENT_SECRET),
                ("GOOGLE_OAUTH_REDIRECT_URI", cls.GOOGLE_OAUTH_REDIRECT_URI),
            ),
            "GitHub": (
                ("GITHUB_CLIENT_ID", cls.GITHUB_OAUTH_CLIENT_ID),
                ("GITHUB_CLIENT_SECRET", cls.GITHUB_OAUTH_CLIENT_SECRET),
                ("GITHUB_OAUTH_REDIRECT_URI", cls.GITHUB_OAUTH_REDIRECT_URI),
            ),
            "Apple": (
                ("APPLE_CLIENT_ID", cls.APPLE_OAUTH_CLIENT_ID),
                ("APPLE_TEAM_ID", cls.APPLE_TEAM_ID),
                ("APPLE_KEY_ID", cls.APPLE_KEY_ID),
                ("APPLE_PRIVATE_KEY", cls.APPLE_PRIVATE_KEY),
                ("APPLE_OAUTH_REDIRECT_URI", cls.APPLE_OAUTH_REDIRECT_URI),
            ),
            "Microsoft": (
                ("MICROSOFT_CLIENT_ID", cls.MICROSOFT_OAUTH_CLIENT_ID),
                ("MICROSOFT_CLIENT_SECRET", cls.MICROSOFT_OAUTH_CLIENT_SECRET),
                ("MICROSOFT_TENANT", cls.MICROSOFT_OAUTH_TENANT),
                ("MICROSOFT_OAUTH_REDIRECT_URI", cls.MICROSOFT_OAUTH_REDIRECT_URI),
            ),
        }
        for provider, fields in oauth_groups.items():
            configured = [name for name, value in fields if value]
            if configured and len(configured) != len(fields):
                missing_names = [name for name, value in fields if not value]
                raise RuntimeError(f"{provider} OAuth configuration is incomplete; missing: {', '.join(missing_names)}.")
            redirect_uri = fields[-1][1]
            if configured and not cls._is_valid_public_url(redirect_uri, require_https=True):
                raise RuntimeError(f"{provider} OAuth redirect URI must be an absolute HTTPS URL in production.")

        if cls.REQUIRE_EMAIL_VERIFICATION:
            mail_fields = (
                ("MAIL_SERVER", cls.MAIL_SERVER), ("MAIL_USERNAME", cls.MAIL_USERNAME),
                ("MAIL_PASSWORD", cls.MAIL_PASSWORD), ("MAIL_DEFAULT_SENDER", cls.MAIL_DEFAULT_SENDER),
            )
            missing_mail = [name for name, value in mail_fields if not value]
            if missing_mail:
                raise RuntimeError(
                    "Email verification requires configured SMTP settings; missing: "
                    + ", ".join(missing_mail)
                    + "."
                )

        for name, value in (
            ("PROVIDER_HTTP_TIMEOUT_SECONDS", cls.PROVIDER_HTTP_TIMEOUT_SECONDS),
            ("OAUTH_HTTP_TIMEOUT_SECONDS", cls.OAUTH_HTTP_TIMEOUT_SECONDS),
            ("CHAT_MAX_PROMPT_CHARS", cls.CHAT_MAX_PROMPT_CHARS),
            ("RESEARCH_QUERY_MAX_CHARS", cls.RESEARCH_QUERY_MAX_CHARS),
            ("RAG_QUERY_MAX_CHARS", cls.RAG_QUERY_MAX_CHARS),
        ):
            if value <= 0:
                raise RuntimeError(f"{name} must be greater than zero.")

        provider_keys = (
            ("GEMINI_API_KEY", cls.GEMINI_API_KEY),
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            ("CLAUDE_API_KEY", cls.CLAUDE_API_KEY),
            ("GROQ_API_KEY", cls.GROQ_API_KEY),
            ("OPENROUTER_API_KEY", cls.OPENROUTER_API_KEY),
            ("DEEPSEEK_API_KEY", cls.DEEPSEEK_API_KEY),
            ("MISTRAL_API_KEY", cls.MISTRAL_API_KEY),
        )
        configured_provider_keys = [
            key_name for key_name, value in provider_keys
            if value and not cls._is_placeholder_secret(value)
        ]
        if not configured_provider_keys:
            raise RuntimeError("At least one supported AI provider API key is required in production.")
        if any(value and cls._is_placeholder_secret(value) for _, value in provider_keys):
            raise RuntimeError("AI provider API keys must not use insecure placeholder values in production.")
        if cls.GEMINI_API_KEY and not cls.GEMINI_MODEL:
            raise RuntimeError("GEMINI_MODEL is required when GEMINI_API_KEY is configured in production.")

        if not cls.RATELIMIT_STORAGE_URI.startswith(("redis://", "rediss://")):
            raise RuntimeError(
                "RATELIMIT_STORAGE_URI must use shared Redis storage in production."
            )
        if not cls.CANCELLATION_REDIS_URL.startswith(("redis://", "rediss://")):
            raise RuntimeError("CANCELLATION_REDIS_URL must use Redis in production.")
        if cls.RAG_STORAGE_BACKEND != "database":
            raise RuntimeError("RAG_STORAGE_BACKEND must be 'database' in production.")
        if cls.STORAGE_BACKEND != "s3":
            raise RuntimeError("STORAGE_BACKEND must be 's3' in production.")
        if not cls.S3_BUCKET:
            raise RuntimeError("S3_BUCKET is required in production.")
        if cls.SQLALCHEMY_DATABASE_URI.startswith("sqlite:"):
            raise RuntimeError("DATABASE_URL must use a multi-worker production database, not SQLite.")


def ensure_runtime_directories() -> None:
    """
    Create runtime directories when they do not exist.
    This keeps local development and deployment startup predictable.
    """
    directories = (
        Config.UPLOAD_FOLDER,
        Config.VECTOR_STORE_DIR,
        Config.LOG_DIR,
    )
    for directory in directories:
        os.makedirs(
            directory,
            exist_ok=True,
        )


Config.validate()
ensure_runtime_directories()
