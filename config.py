"""Configuration sourced from the environment where appropriate."""
import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-me-before-deploying"
    DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "users.db"))
    UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", BASE_DIR / "static" / "uploads"))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "pdf"}
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    SOCKETIO_ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE") or None
    DEBUG = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
