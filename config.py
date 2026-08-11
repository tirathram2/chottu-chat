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
    # Keep the production server independent of eventlet.  When this is left
    # as None Flask-SocketIO auto-selects eventlet simply because it is
    # installed, even when Gunicorn is not using an eventlet worker.
    SOCKETIO_ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE", "threading")
    # Render supports WebSocket upgrades. Polling remains enabled as a
    # fallback for clients or networks that cannot establish a WebSocket.
    SOCKETIO_TRANSPORTS = ("websocket", "polling")
    DEBUG = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
