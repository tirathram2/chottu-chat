
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import check_password_hash, generate_password_hash


# -------------------- App configuration --------------------
BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "chatwave.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["JSON_SORT_KEYS"] = False

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
)

login_manager = LoginManager()
login_manager.init_app(app)

online_users = set()


# -------------------- Database --------------------
def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def setup_database():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                avatar TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER,
                content TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',
                seen INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(sender_id) REFERENCES users(id),
                FOREIGN KEY(receiver_id) REFERENCES users(id)
            )
        """)


# -------------------- User model --------------------
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["id"])
        self.name = user_data["name"]
        self.email = user_data["email"]
        self.avatar = user_data["avatar"] or ""


@login_manager.user_loader
def load_user(user_id):
    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    return User(user) if user else None


# -------------------- Helper functions --------------------
def now():
    return datetime.now(timezone.utc).isoformat()


def user_to_dict(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "avatar": user["avatar"] or "",
        "online": user["id"] in online_users,
    }


def message_to_dict(message):
    return {
        "id": message["id"],
        "sender_id": message["sender_id"],
        "receiver_id": message["receiver_id"],
        "content": message["content"],
        "message_type": message["message_type"],
        "seen": bool(message["seen"]),
        "created_at": message["created_at"],
        "sender_name": message["sender_name"],
        "sender_avatar": message["sender_avatar"] or "",
    }


# -------------------- HTML pages --------------------
@app.route("/")
def home():
    if current_user.is_authenticated:
        return send_from_directory(BASE_DIR, "index.html")
    return send_from_directory(BASE_DIR, "login.html")


@app.route("/login.html")
def login_page():
    return send_from_directory(BASE_DIR, "login.html")


@app.route("/signup.html")
def signup_page():
    return send_from_directory(BASE_DIR, "signup.html")


@app.route("/index.html")
@login_required
def chat_page():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    allowed_extensions = (".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico")
    if filename.endswith(allowed_extensions):
        return send_from_directory(BASE_DIR, filename)
    return jsonify({"error": "File not found"}), 404


# -------------------- Authentication API --------------------
@app.post("/api/signup")
def signup():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if len(name) < 2:
        return jsonify({"error": "Name must be at least 2 characters."}), 400

    if "@" not in email:
        return jsonify({"error": "Please enter a valid email."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    try:
        with get_db() as db:
            cursor = db.execute(
                """
                INSERT INTO users (name, email, password, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, generate_password_hash(password), now()),
            )
            user_id = cursor.lastrowid

            user = db.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()

        login_user(User(user))
        return jsonify({"message": "Account created successfully.", "user": user_to_dict(user)}), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "This email is already registered."}), 409


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Incorrect email or password."}), 401

    login_user(User(user), remember=bool(data.get("remember", False)))
    return jsonify({"message": "Login successful.", "user": user_to_dict(user)})


@app.post("/api/logout")
@login_required
def logout():
    online_users.discard(int(current_user.id))
    socketio.emit("user_status", {
        "user_id": int(current_user.id),
        "online": False,
    })

    logout_user()
    return jsonify({"message": "Logged out successfully."})


@app.get("/api/me")
def get_me():
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False}), 401

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE id = ?", (current_user.id,)
        ).fetchone()

    return jsonify({"authenticated": True, "user": user_to_dict(user)})


# -------------------- Chat API --------------------
@app.get("/api/users")
@login_required
def get_users():
    search = request.args.get("search", "").strip()

    with get_db() as db:
        users = db.execute(
            """
            SELECT id, name, email, avatar
            FROM users
            WHERE id != ?
              AND (name LIKE ? OR email LIKE ?)
            ORDER BY name ASC
            """,
            (current_user.id, f"%{search}%", f"%{search}%"),
        ).fetchall()

    return jsonify({"users": [user_to_dict(user) for user in users]})


@app.get("/api/messages/global")
@login_required
def global_messages():
    with get_db() as db:
        messages = db.execute(
            """
            SELECT m.*, u.name AS sender_name, u.avatar AS sender_avatar
            FROM messages m
            JOIN users u ON u.id = m.sender_id
            WHERE m.receiver_id IS NULL
            ORDER BY m.id DESC
            LIMIT 100
            """
        ).fetchall()

    return jsonify({"messages": [message_to_dict(m) for m in reversed(messages)]})


@app.get("/api/messages/private/<int:user_id>")
@login_required
def private_messages(user_id):
    with get_db() as db:
        messages = db.execute(
            """
            SELECT m.*, u.name AS sender_name, u.avatar AS sender_avatar
            FROM messages m
            JOIN users u ON u.id = m.sender_id
            WHERE (m.sender_id = ? AND m.receiver_id = ?)
               OR (m.sender_id = ? AND m.receiver_id = ?)
            ORDER BY m.id ASC
            LIMIT 100
            """,
            (current_user.id, user_id, user_id, current_user.id),
        ).fetchall()

        db.execute(
            """
            UPDATE messages
            SET seen = 1
            WHERE sender_id = ? AND receiver_id = ?
            """,
            (user_id, current_user.id),
        )

    socketio.emit("messages_seen", {
        "by_user_id": int(current_user.id),
        "for_user_id": user_id,
    }, room=f"user_{user_id}")

    return jsonify({"messages": [message_to_dict(m) for m in messages]})


# -------------------- Real-time socket events --------------------
@socketio.on("connect")
def on_connect():
    if not current_user.is_authenticated:
        return False

    user_id = int(current_user.id)
    online_users.add(user_id)
    join_room(f"user_{user_id}")

    emit("user_status", {"user_id": user_id, "online": True}, broadcast=True)


@socketio.on("disconnect")
def on_disconnect():
    if current_user.is_authenticated:
        user_id = int(current_user.id)
        online_users.discard(user_id)

        socketio.emit("user_status", {
            "user_id": user_id,
            "online": False,
        })


@socketio.on("typing")
def typing(data):
    if not current_user.is_authenticated:
        return

    receiver_id = data.get("receiver_id")
    is_typing = bool(data.get("is_typing", False))

    if receiver_id:
        emit("typing", {
            "user_id": int(current_user.id),
            "name": current_user.name,
            "is_typing": is_typing,
        }, room=f"user_{int(receiver_id)}")


@socketio.on("send_message")
def send_message(data):
    if not current_user.is_authenticated:
        return

    content = str(data.get("content", "")).strip()
    receiver_id = data.get("receiver_id")  # null = global chat
    message_type = str(data.get("message_type", "text"))

    if not content or len(content) > 2000:
        emit("chat_error", {"error": "Message must be between 1 and 2000 characters."})
        return

    if receiver_id is not None:
        try:
            receiver_id = int(receiver_id)
        except (ValueError, TypeError):
            emit("chat_error", {"error": "Invalid receiver."})
            return

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO messages
            (sender_id, receiver_id, content, message_type, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (current_user.id, receiver_id, content, message_type, now()),
        )
        message_id = cursor.lastrowid

        message = db.execute(
            """
            SELECT m.*, u.name AS sender_name, u.avatar AS sender_avatar
            FROM messages m
            JOIN users u ON u.id = m.sender_id
            WHERE m.id = ?
            """,
            (message_id,),
        ).fetchone()

    payload = message_to_dict(message)

    if receiver_id is None:
        emit("new_message", payload, broadcast=True)
    else:
        emit("new_message", payload, room=f"user_{int(current_user.id)}")
        emit("new_message", payload, room=f"user_{receiver_id}")


# -------------------- Start server --------------------
if __name__ == "__main__":
    setup_database()

    port = int(os.environ.get("PORT", 5000))

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True,
    )
