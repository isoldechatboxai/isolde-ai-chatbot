import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


class Config:
    # --- Core ---
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"
    
    # Environment detection
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    IS_PRODUCTION = FLASK_ENV == "production"

    # --- Database - Neon/PostgreSQL Production Configuration ---
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'isolde.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Critical fix for serverless PostgreSQL (Neon/Render): connection pooling & SSL stability
    # Only apply pooling options for PostgreSQL databases to avoid SQLite errors
    _db_uri = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'isolde.db')}")
    _is_postgresql = _db_uri.startswith("postgresql")
    if _is_postgresql:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 3600,
            "pool_size": 10,
            "max_overflow": 20,
            "connect_args": {
                "sslmode": "require",
                "connect_timeout": 10,
                "application_name": "isolde-ai-chatbot"
            }
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {}

    # --- JWT ---
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MIN", 60))
    )

    # --- Gemini ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # --- Uploads ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, os.getenv("UPLOAD_FOLDER", "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", 16)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "csv", "xlsx", "png", "jpg", "jpeg"}

    # --- CORS ---
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

    # --- Vector store (simple local store; swap for Chroma/FAISS/Pinecone) ---
    VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")

    # --- Logging ---
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    
    # --- Redis (for rate limiting & caching) ---
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # --- Video Provider ---
    VIDEO_PROVIDER_KEY = os.getenv("VIDEO_PROVIDER_KEY", "")
    
    # --- Rate Limiting ---
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "True") == "True"
    RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", None) or REDIS_URL if IS_PRODUCTION else "memory://"
