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