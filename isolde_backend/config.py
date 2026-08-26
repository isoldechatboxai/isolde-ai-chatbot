import os
import re
from datetime import timedelta

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

    MAIL_SERVER = os.getenv("MAIL_SERVER", "").strip()
    MAIL_PORT = _env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", default=True)
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

    @classmethod
    def validate(cls) -> None:
        """
        Validate required production configuration.

        Development can run without external secrets so that local
        development and repository setup remain possible.
        Production must fail fast when critical configuration is missing.
        """
        if not cls.IS_PRODUCTION:
            return

        missing = []
        unsafe = []

        for key_name, value in (
            ("FLASK_SECRET_KEY", cls.SECRET_KEY),
            ("JWT_SECRET_KEY", cls.JWT_SECRET_KEY),
            ("GEMINI_API_KEY", cls.GEMINI_API_KEY),
            ("GEMINI_MODEL", cls.GEMINI_MODEL),
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

        if unsafe:
            raise RuntimeError(
                "Production secrets must not use empty or insecure placeholder values: "
                + ", ".join(unsafe)
            )

        if cls.RATELIMIT_STORAGE_URI == "memory://":
            raise RuntimeError(
                "RATELIMIT_STORAGE_URI must use shared storage such as Redis in production."
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
