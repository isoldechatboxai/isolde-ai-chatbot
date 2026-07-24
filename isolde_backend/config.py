import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


class Config:
    # --- Core ---
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.getenv("FLASK_DEBUG", "True") == "True"

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'isolde.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- JWT ---
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MIN", 60))
    )

    # --- Gemini ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

    # --- Uploads ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, os.getenv("UPLOAD_FOLDER", "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", 15)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "csv", "xlsx", "png", "jpg", "jpeg"}

    # --- CORS ---
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    # --- Vector store (simple local store; swap for Chroma/FAISS/Pinecone) ---
    VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")

    # --- Logging ---
    LOG_DIR = os.path.join(BASE_DIR, "logs")
