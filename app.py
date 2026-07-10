import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_socketio import SocketIO, emit, join_room
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "chottu_chat.db"
UPLOAD_DIRECTORY = BASE_DIR / "uploads"
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "mp4",
    "webm",
    "mov",
    "pdf",
}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}
MAX_UPLOAD_SIZE = 25 * 1024 * 1024

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get(
        "SECRET_KEY", "replace-this-development-secret-before-deploying"
    ),
    MAX_CONTENT_LENGTH=MAX_UPLOAD_SIZE,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

socketio = SocketIO(
    app,
    cors_allowed_origins=os.environ.get("SOCKETIO_CORS_ALLOWED_ORIGINS", "*"),
    async_mode=os.environ.get("SOCKETIO_ASYNC_MODE", "threading"),
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "error"

online_connections = {}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                avatar TEXT,
                bio TEXT NOT NULL DEFAULT '',
                theme TEXT NOT NULL DEFAULT 'dark',
                last_seen TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER,
                body TEXT NOT NULL DEFAULT '',
                attachment TEXT,
                attachment_type TEXT,
                created_at TEXT NOT NULL,
                seen_at TEXT,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_global
            ON messages (recipient_id, id DESC);

            CREATE INDEX IF NOT EXISTS idx_messages_private
            ON messages (sender_id, recipient_id, id DESC);
            """
        )


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.email = row["email"]
        self.password_hash = row["password_hash"]
        self.avatar = row["avatar"]
        self.bio = row["bio"]
        self.theme = row["theme"]
        self.last_seen = row["last_seen"]
        self.created_at = row["created_at"]

    @property
    def is_online(self):
        return bool(online_connections.get(self.id))


@login_manager.user_loader
def load_user(user_id):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    with get_db() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    return User(row) if row else None


def get_user_row(user_id):
    with get_db() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def allowed_file(filename):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def attachment_category(filename):
    extension = filename.rsplit(".", 1)[1].lower()

    if extension in IMAGE_EXTENSIONS:
        return "image"

    if extension in VIDEO_EXTENSIONS:
        return "video"

    return "document"


def avatar_url(filename):
    if not filename:
        return url_for("static", filename="default.png")

    return url_for("uploaded_file", filename=filename)


def serialize_user(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "bio": row["bio"] or "",
        "avatar": row["avatar"] or "",
        "avatar_url": avatar_url(row["avatar"]),
        "online": bool(online_connections.get(row["id"])),
        "last_seen": row["last_seen"],
    }


def serialize_message(row):
    attachment = row["attachment"]
    return {
        "id": row["id"],
        "sender_id": row["sender_id"],
        "recipient_id": row["recipient_id"],
        "body": row["body"] or "",
        "attachment": attachment,
        "attachment_url": (
            url_for("uploaded_file", filename=attachment) if attachment else None
        ),
        "attachment_type": row["attachment_type"],
        "created_at": row["created_at"],
        "seen_at": row["seen_at"],
        "seen": bool(row["seen_at"]),
    }


def private_room(user_id):
    return f"user:{user_id}"


def user_exists(user_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    return row is not None


def current_presence_payload(user_id, online):
    return {"user_id": user_id, "online": online, "last_seen": now_iso() if not online else None}


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("chat"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("chat"))

    if request.method == "POST":
        identity = request.form.get("identity", "").strip().lower()
        password = request.form.get("password", "")

        if not identity or not password:
            flash("Enter your username or email and password.", "error")
            return render_template("login.html")

        with get_db() as connection:
            row = connection.execute(
                """
                SELECT * FROM users
                WHERE lower(username) = ? OR lower(email) = ?
                """,
                (identity, identity),
            ).fetchone()

        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row), remember=request.form.get("remember") == "on")
            return redirect(request.args.get("next") or url_for("chat"))

        flash("Incorrect username, email, or password.", "error")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("chat"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if len(username) < 3 or len(username) > 30:
            flash("Username must contain 3 to 30 characters.", "error")
        elif not username.replace("_", "").replace(".", "").isalnum():
            flash(
                "Username can contain only letters, numbers, dots, and underscores.",
                "error",
            )
        elif "@" not in email or len(email) > 254:
            flash("Enter a valid email address.", "error")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        else:
            try:
                with get_db() as connection:
                    cursor = connection.execute(
                        """
                        INSERT INTO users (
                            username,
                            email,
                            password_hash,
                            created_at
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            username,
                            email,
                            generate_password_hash(password),
                            now_iso(),
                        ),
                    )
                    user_id = cursor.lastrowid
                    row = connection.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()

                login_user(User(row))
                return redirect(url_for("chat"))
            except sqlite3.IntegrityError:
                flash("That username or email address is already in use.", "error")

    return render_template("signup.html")


@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.get("/chat")
@login_required
def chat():
    return render_template("index.html")


@app.get("/api/me")
@login_required
def get_current_user():
    row = get_user_row(current_user.id)

    if not row:
        abort(404)

    return jsonify(serialize_user(row))


@app.get("/api/users")
@login_required
def get_users():
    query = request.args.get("q", "").strip().lower()
    wildcard_query = f"%{query}%"

    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT id, username, bio, avatar, last_seen
            FROM users
            WHERE id != ?
              AND (lower(username) LIKE ? OR lower(email) LIKE ?)
            ORDER BY lower(username) ASC
            LIMIT 100
            """,
            (current_user.id, wildcard_query, wildcard_query),
        ).fetchall()

    return jsonify([serialize_user(row) for row in rows])


@app.get("/api/users/<int:user_id>")
@login_required
def get_user(user_id):
    if user_id == current_user.id:
        row = get_user_row(current_user.id)
    else:
        with get_db() as connection:
            row = connection.execute(
                """
                SELECT id, username, bio, avatar, last_seen
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

    if not row:
        return jsonify({"error": "User not found."}), 404

    return jsonify(serialize_user(row))


@app.get("/api/messages/global")
@login_required
def get_global_messages():
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM messages
            WHERE recipient_id IS NULL
            ORDER BY id DESC
            LIMIT 100
            """
        ).fetchall()

    messages = [serialize_message(row) for row in reversed(rows)]
    return jsonify(messages)


@app.get("/api/messages/private/<int:user_id>")
@login_required
def get_private_messages(user_id):
    if user_id == current_user.id:
        return jsonify({"error": "You cannot create a private chat with yourself."}), 400

    if not user_exists(user_id):
        return jsonify({"error": "User not found."}), 404

    seen_at = now_iso()

    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM messages
            WHERE (
                sender_id = ?
                AND recipient_id = ?
            )
            OR (
                sender_id = ?
                AND recipient_id = ?
            )
            ORDER BY id DESC
            LIMIT 100
            """,
            (current_user.id, user_id, user_id, current_user.id),
        ).fetchall()

        connection.execute(
            """
            UPDATE messages
            SET seen_at = ?
            WHERE sender_id = ?
              AND recipient_id = ?
              AND seen_at IS NULL
            """,
            (seen_at, user_id, current_user.id),
        )

    if rows:
        socketio.emit(
            "messages_seen",
            {
                "reader_id": current_user.id,
                "sender_id": user_id,
                "seen_at": seen_at,
            },
            room=private_room(user_id),
        )

    messages = [serialize_message(row) for row in reversed(rows)]
    return jsonify(messages)


@app.get("/api/search/messages")
@login_required
def search_messages():
    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify([])

    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM messages
            WHERE body LIKE ?
              AND (
                  sender_id = ?
                  OR recipient_id = ?
                  OR recipient_id IS NULL
              )
            ORDER BY id DESC
            LIMIT 50
            """,
            (f"%{query}%", current_user.id, current_user.id),
        ).fetchall()

    return jsonify([serialize_message(row) for row in rows])


@app.post("/api/upload")
@login_required
def upload_attachment():
    file = request.files.get("attachment")

    if not file or not file.filename:
        return jsonify({"error": "Choose a file to upload."}), 400

    if not allowed_file(file.filename):
        return jsonify(
            {"error": "Only images, videos, and PDF files can be uploaded."}
        ), 400

    original_name = secure_filename(file.filename)

    if not original_name:
        return jsonify({"error": "Invalid file name."}), 400

    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    file.save(UPLOAD_DIRECTORY / unique_name)

    return jsonify(
        {
            "name": unique_name,
            "url": url_for("uploaded_file", filename=unique_name),
            "category": attachment_category(unique_name),
            "mime_type": file.mimetype,
        }
    )


@app.post("/api/profile")
@login_required
def update_profile():
    bio = request.form.get("bio", "").strip()[:180]
    theme = request.form.get("theme", "dark").strip().lower()
    avatar_file = request.files.get("avatar")

    if theme not in {"dark", "light"}:
        return jsonify({"error": "Invalid appearance preference."}), 400

    avatar_name = current_user.avatar

    if avatar_file and avatar_file.filename:
        if not allowed_file(avatar_file.filename):
            return jsonify({"error": "Choose a valid image file."}), 400

        extension = avatar_file.filename.rsplit(".", 1)[1].lower()

        if extension not in IMAGE_EXTENSIONS:
            return jsonify({"error": "Profile photo must be an image."}), 400

        safe_name = secure_filename(avatar_file.filename)

        if not safe_name:
            return jsonify({"error": "Invalid image name."}), 400

        avatar_name = f"{uuid.uuid4().hex}_{safe_name}"
        avatar_file.save(UPLOAD_DIRECTORY / avatar_name)

    with get_db() as connection:
        connection.execute(
            """
            UPDATE users
            SET bio = ?, theme = ?, avatar = ?
            WHERE id = ?
            """,
            (bio, theme, avatar_name, current_user.id),
        )
        row = connection.execute(
            "SELECT * FROM users WHERE id = ?", (current_user.id,)
        ).fetchone()

    return jsonify(serialize_user(row))


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIRECTORY, filename, as_attachment=False)


@app.errorhandler(RequestEntityTooLarge)
def handle_large_upload(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "The maximum upload size is 25 MB."}), 413

    flash("The maximum upload size is 25 MB.", "error")
    return redirect(request.referrer or url_for("chat"))


@socketio.on("connect")
def handle_connect():
    if not current_user.is_authenticated:
        return False

    user_id = current_user.id
    sid = request.sid
    was_offline = not bool(online_connections.get(user_id))

    online_connections.setdefault(user_id, set()).add(sid)

    join_room("global")
    join_room(private_room(user_id))

    if was_offline:
        emit(
            "presence",
            current_presence_payload(user_id, True),
            broadcast=True,
            include_self=False,
        )


@socketio.on("disconnect")
def handle_disconnect():
    if not current_user.is_authenticated:
        return

    user_id = current_user.id
    sid = request.sid
    connections = online_connections.get(user_id, set())

    connections.discard(sid)

    if connections:
        online_connections[user_id] = connections
        return

    online_connections.pop(user_id, None)
    timestamp = now_iso()

    with get_db() as connection:
        connection.execute(
            "UPDATE users SET last_seen = ? WHERE id = ?",
            (timestamp, user_id),
        )

    emit(
        "presence",
        {"user_id": user_id, "online": False, "last_seen": timestamp},
        broadcast=True,
    )


@socketio.on("send_message")
def handle_send_message(data):
    if not current_user.is_authenticated:
        return

    if not isinstance(data, dict):
        emit("message_error", {"error": "Invalid message data."})
        return

    body = str(data.get("body", "")).strip()[:3000]
    attachment = data.get("attachment")
    attachment_type = data.get("attachment_type")
    recipient_id = data.get("recipient_id")

    if not body and not attachment:
        return

    if attachment:
        attachment = secure_filename(str(attachment))

        if not attachment or not (UPLOAD_DIRECTORY / attachment).is_file():
            emit("message_error", {"error": "The shared file is unavailable."})
            return

        if not allowed_file(attachment):
            emit("message_error", {"error": "Invalid shared file."})
            return

        attachment_type = attachment_type or attachment_category(attachment)

    if recipient_id in (None, "", "global"):
        recipient_id = None
    else:
        try:
            recipient_id = int(recipient_id)
        except (TypeError, ValueError):
            emit("message_error", {"error": "Invalid recipient."})
            return

        if recipient_id == current_user.id or not user_exists(recipient_id):
            emit("message_error", {"error": "Invalid recipient."})
            return

    with get_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO messages (
                sender_id,
                recipient_id,
                body,
                attachment,
                attachment_type,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                current_user.id,
                recipient_id,
                body,
                attachment,
                attachment_type,
                now_iso(),
            ),
        )

        row = connection.execute(
            "SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()

    payload = serialize_message(row)

    if recipient_id is None:
        socketio.emit("new_message", payload, room="global")
    else:
        socketio.emit("new_message", payload, room=private_room(current_user.id))
        socketio.emit("new_message", payload, room=private_room(recipient_id))


@socketio.on("typing")
def handle_typing(data):
    if not current_user.is_authenticated or not isinstance(data, dict):
        return

    recipient_id = data.get("recipient_id")

    try:
        recipient_id = int(recipient_id)
    except (TypeError, ValueError):
        return

    if recipient_id == current_user.id or not user_exists(recipient_id):
        return

    emit(
        "typing",
        {
            "user_id": current_user.id,
            "typing": bool(data.get("typing")),
        },
        room=private_room(recipient_id),
    )


@socketio.on("mark_seen")
def handle_mark_seen(data):
    if not current_user.is_authenticated or not isinstance(data, dict):
        return

    sender_id = data.get("sender_id")

    try:
        sender_id = int(sender_id)
    except (TypeError, ValueError):
        return

    if sender_id == current_user.id or not user_exists(sender_id):
        return

    timestamp = now_iso()

    with get_db() as connection:
        connection.execute(
            """
            UPDATE messages
            SET seen_at = ?
            WHERE sender_id = ?
              AND recipient_id = ?
              AND seen_at IS NULL
            """,
            (timestamp, sender_id, current_user.id),
        )

    socketio.emit(
        "messages_seen",
        {
            "reader_id": current_user.id,
            "sender_id": sender_id,
            "seen_at": timestamp,
        },
        room=private_room(sender_id),
    )


@socketio.on("webrtc_signal")
def handle_webrtc_signal(data):
    if not current_user.is_authenticated or not isinstance(data, dict):
        return

    target_id = data.get("target_id")
    signal = data.get("signal")
    call_type = data.get("call_type", "voice")

    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        return

    if (
        target_id == current_user.id
        or not user_exists(target_id)
        or call_type not in {"voice", "video"}
        or not isinstance(signal, dict)
    ):
        return

    emit(
        "webrtc_signal",
        {
            "from_id": current_user.id,
            "call_type": call_type,
            "signal": signal,
        },
        room=private_room(target_id),
    )


init_db()

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )


12:29 AM
