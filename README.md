# Chottu Chat

A real-time Flask and Socket.IO chat application that preserves the existing responsive user interface.

## Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`, create two accounts, and use two browser windows to test private and global chat.

## Production / Render

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --bind 0.0.0.0:$PORT --worker-class gthread --workers 1 --threads 100 app:app`
- Required environment variable: `SECRET_KEY` (a long random value)

Optional environment variables: `DATABASE_PATH`, `MAX_UPLOAD_BYTES`, `CORS_ORIGINS`, `SOCKETIO_ASYNC_MODE`, and `FLASK_DEBUG`. `SOCKETIO_ASYNC_MODE` defaults to `threading`; do not set it to `eventlet`. For persistent Render data, mount a disk and set `DATABASE_PATH` on that disk. SQLite is appropriate for one instance; use managed storage/database services before scaling horizontally.

## Structure

```
app.py                 Application factory and production entry point
config.py              Environment-backed application configuration
database.py            SQLite schema, safe migration, and User model
auth.py                Signup, login, logout, Flask-Login integration
routes.py              HTTP and authenticated JSON API routes
socket_events.py       Socket.IO presence, messages, typing, call signaling
upload.py              Secure upload validation and storage
utils.py               Shared validation and serialization helpers
templates/             Login, signup, error, and application UI
static/                Existing CSS, JavaScript, assets, and runtime uploads
```

## Security notes

Passwords use Werkzeug hashes. User IDs are always derived from the authenticated session, SQL is parameterized, uploads use generated safe filenames with extension and size restrictions, and user message text is escaped in the browser.
