# ======================================================
# CHOTTU CHAT
# Professional Flask Server
# STEP 1
# ======================================================

import os
import sqlite3
import secrets
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    session,
    flash
)

from flask_socketio import (
    SocketIO,
    emit,
    join_room,
    leave_room
)

from werkzeug.utils import secure_filename
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

BASE_DIR = Path(__file__).resolve().parent

DATABASE = BASE_DIR / "chat.db"

UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
PROFILE_FOLDER = BASE_DIR / "static" / "avatars"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_FOLDER, exist_ok=True)

app = Flask(__name__)

app.secret_key = secrets.token_hex(32)

app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)
# ======================================================
# DATABASE FUNCTIONS
# STEP 2
# ======================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():

    conn = get_db()

    cursor = conn.cursor()

    # =========================
    # USERS
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        username TEXT UNIQUE NOT NULL,

        email TEXT UNIQUE,

        password TEXT NOT NULL,

        avatar TEXT DEFAULT '',

        bio TEXT DEFAULT '',

        online INTEGER DEFAULT 0,

        created_at TEXT
        last_seen TEXT DEFAULT ''

    )
    """)

    # =========================
    # PRIVATE MESSAGES
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        sender TEXT,

        receiver TEXT,

        message TEXT,

        image TEXT,

        video TEXT,

        pdf TEXT,

        seen INTEGER DEFAULT 0,

        created_at TEXT

    )
    """)

    # =========================
    # GROUPS
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        group_name TEXT,

        group_image TEXT,

        owner TEXT,

        created_at TEXT

    )
    """)

    # =========================
    # GROUP MEMBERS
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_members(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        group_id INTEGER,

        username TEXT

    )
    """)

    # =========================
    # GROUP MESSAGES
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_messages(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        group_id INTEGER,

        sender TEXT,

        message TEXT,

        image TEXT,

        video TEXT,

        pdf TEXT,

        created_at TEXT

    )
    """)

    conn.commit()

    conn.close()


init_database()
# ======================================================
# LOGIN / SIGNUP SYSTEM
# STEP 3
# ======================================================

@app.route("/")
def home():

    if "user" in session:
        return redirect(url_for("chat"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"].strip()

        password = request.form["password"]

        conn = get_db()

        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        )

        user = cursor.fetchone()

        conn.close()

        if user is None:

            flash("Username not found")

            return redirect(url_for("login"))

        if not check_password_hash(
            user["password"],
            password
        ):

            flash("Wrong password")

            return redirect(url_for("login"))

        session["user"] = user["username"]

        return redirect(url_for("chat"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"].strip()

        email = request.form["email"].strip()

        password = request.form["password"]

        hash_password = generate_password_hash(password)

        conn = get_db()

        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO users
                (
                    username,
                    email,
                    password,
                    created_at
                )

                VALUES
                (
                    ?, ?, ?, ?
                )
                """,

                (
                    username,
                    email,
                    hash_password,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

            )

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            flash("Username already exists")

            return redirect(url_for("signup"))

        conn.close()

        flash("Account created successfully")

        return redirect(url_for("login"))

    return render_template("signup.html")
# ======================================================
# CHAT ROUTES & USER API
# STEP 4
# ======================================================

@app.route("/chat")
def chat():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template(
        "index.html",
        username=session["user"]
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


@app.route("/api/me")
def api_me():

    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE username=?",
        (session["user"],)
    )

    user = cursor.fetchone()

    conn.close()

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({

        "id": user["id"],

        "username": user["username"],

        "email": user["email"],

        "avatar": user["avatar"],

        "bio": user["bio"],

        "online": user["online"]

    })


@app.route("/api/users")
def api_users():

    if "user" not in session:
        return jsonify([])

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
        id,
        username,
        avatar,
        bio,
        online
        FROM users
        WHERE username != ?
        ORDER BY username
        """,
        (session["user"],)
    )

    users = cursor.fetchall()

    conn.close()

    data = []

    for user in users:

        data.append({

            "id": user["id"],

            "username": user["username"],

            "avatar": user["avatar"],

            "bio": user["bio"],

            "online": bool(user["online"])

        })

    return jsonify(data)
# ======================================================
# SOCKET.IO REAL-TIME CHAT
# STEP 5
# ======================================================

@socketio.on("send_message")
def send_message(data):

    sender = session["user"]

    receiver = data.get("receiver")

    message = data.get("message", "").strip()

    if message == "":
        return

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO messages
        (
            sender,
            receiver,
            message,
            created_at
        )

        VALUES
        (
            ?, ?, ?, ?
        )
        """,
        (
            sender,
            receiver,
            message,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    message_id = cursor.lastrowid

    conn.commit()

    conn.close()

    emit(
        "receive_message",
        {
            "id": message_id,
            "sender": sender,
            "receiver": receiver,
            "message": message,
            "time": datetime.now().strftime("%H:%M")
        },
        room=receiver
    )

    emit(
        "receive_message",
        {
            "id": message_id,
            "sender": sender,
            "receiver": receiver,
            "message": message,
            "time": datetime.now().strftime("%H:%M")
        },
        room=sender
     )
# ======================================================
# FILE UPLOAD SYSTEM
# STEP 6
# ======================================================

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "mp4",
    "webm",
    "pdf"
}


def allowed_file(filename):

    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@app.route("/upload", methods=["POST"])
def upload_file():

    if "user" not in session:
        return jsonify({
            "success": False
        }), 401

    if "file" not in request.files:

        return jsonify({
            "success": False,
            "message": "No file selected"
        })

    file = request.files["file"]

    if file.filename == "":

        return jsonify({
            "success": False,
            "message": "Empty filename"
        })

    if not allowed_file(file.filename):

        return jsonify({
            "success": False,
            "message": "File type not allowed"
        })

    ext = file.filename.rsplit(".", 1)[1].lower()

    filename = (
        uuid4().hex +
        "." +
        ext
    )

    save_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(save_path)

    file_url = "/static/uploads/" + filename

    if ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        file_type = "image"

    elif ext in ["mp4", "webm"]:
        file_type = "video"

    else:
        file_type = "pdf"

    return jsonify({

        "success": True,

        "url": file_url,

        "type": file_type

    })
# ======================================================
# SOCKET.IO FILE MESSAGE SYSTEM
# STEP 7
# ======================================================

@socketio.on("send_file")
def send_file(data):

    if "user" not in session:
        return

    sender = session["user"]

    receiver = data.get("receiver")

    file_url = data.get("url")

    file_type = data.get("type")

    if not file_url:
        return

    conn = get_db()

    cursor = conn.cursor()

    image = None
    video = None
    pdf = None

    if file_type == "image":
        image = file_url

    elif file_type == "video":
        video = file_url

    elif file_type == "pdf":
        pdf = file_url

    cursor.execute(
        """
        INSERT INTO messages
        (
            sender,
            receiver,
            message,
            image,
            video,
            pdf,
            created_at
        )

        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            sender,
            receiver,
            "",
            image,
            video,
            pdf,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    message_id = cursor.lastrowid

    conn.commit()
    conn.close()

    payload = {

        "id": message_id,

        "sender": sender,

        "receiver": receiver,

        "message": "",

        "image": image,

        "video": video,

        "pdf": pdf,

        "time": datetime.now().strftime("%H:%M")
    }

    emit(
        "receive_file",
        payload,
        room=receiver
    )

    emit(
        "receive_file",
        payload,
        room=sender
    )
# ======================================================
# SEEN / READ RECEIPT SYSTEM
# STEP 8
# ======================================================

@socketio.on("message_seen")
def message_seen(data):

    if "user" not in session:
        return

    message_id = data.get("message_id")

    if not message_id:
        return

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE messages
        SET seen=1
        WHERE id=?
        """,
        (message_id,)
    )

    cursor.execute(
        """
        SELECT sender
        FROM messages
        WHERE id=?
        """,
        (message_id,)
    )

    row = cursor.fetchone()

    conn.commit()
    conn.close()

    if row:

        emit(
            "message_seen",
            {
                "message_id": message_id
            },
            room=row["sender"]
        )


@app.route("/api/messages/<username>")
def get_messages(username):

    if "user" not in session:
        return jsonify([])

    me = session["user"]

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM messages

        WHERE

        (sender=? AND receiver=?)

        OR

        (sender=? AND receiver=?)

        ORDER BY id ASC
        """,
        (
            me,
            username,
            username,
            me
        )
    )

    rows = cursor.fetchall()

    conn.close()

    messages = []

    for row in rows:

        messages.append({

            "id": row["id"],

            "sender": row["sender"],

            "receiver": row["receiver"],

            "message": row["message"],

            "image": row["image"],

            "video": row["video"],

            "pdf": row["pdf"],

            "seen": row["seen"],

            "time": row["created_at"]

        })

    return jsonify(messages)
# ======================================================
# MESSAGE REACTION SYSTEM
# STEP 9
# ======================================================

@socketio.on("add_reaction")
def add_reaction(data):

    if "user" not in session:
        return

    message_id = data.get("message_id")
    emoji = data.get("emoji")

    if not message_id or not emoji:
        return

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            username TEXT,
            emoji TEXT
        )
    """)

    cursor.execute("""
        DELETE FROM reactions
        WHERE message_id=? AND username=?
    """, (
        message_id,
        session["user"]
    ))

    cursor.execute("""
        INSERT INTO reactions(
            message_id,
            username,
            emoji
        )
        VALUES(?,?,?)
    """, (
        message_id,
        session["user"],
        emoji
    ))

    conn.commit()

    cursor.execute("""
        SELECT emoji,COUNT(*) total
        FROM reactions
        WHERE message_id=?
        GROUP BY emoji
    """, (message_id,))

    rows = cursor.fetchall()

    conn.close()

    emit(
        "reaction_update",
        {
            "message_id": message_id,
            "reactions": [
                {
                    "emoji": r["emoji"],
                    "count": r["total"]
                }
                for r in rows
            ]
        },
        broadcast=True
    )


@app.route("/api/reactions/<int:message_id>")
def api_reactions(message_id):

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT emoji,
        COUNT(*) total
        FROM reactions
        WHERE message_id=?
        GROUP BY emoji
    """, (message_id,))

    rows = cursor.fetchall()

    conn.close()

    return jsonify([
        {
            "emoji": r["emoji"],
            "count": r["total"]
        }
        for r in rows
    ])
# ======================================================
# VOICE & VIDEO CALL SIGNALING
# STEP 10
# ======================================================

@socketio.on("call_user")
def call_user(data):

    if "user" not in session:
        return

    caller = session["user"]
    receiver = data.get("receiver")
    call_type = data.get("type", "voice")

    emit(
        "incoming_call",
        {
            "caller": caller,
            "type": call_type
        },
        room=receiver
    )


@socketio.on("accept_call")
def accept_call(data):

    if "user" not in session:
        return

    receiver = session["user"]
    caller = data.get("caller")

    emit(
        "call_accepted",
        {
            "receiver": receiver
        },
        room=caller
    )


@socketio.on("reject_call")
def reject_call(data):

    if "user" not in session:
        return

    receiver = session["user"]
    caller = data.get("caller")

    emit(
        "call_rejected",
        {
            "receiver": receiver
        },
        room=caller
    )


@socketio.on("end_call")
def end_call(data):

    if "user" not in session:
        return

    other = data.get("other")

    emit(
        "call_ended",
        {
            "user": session["user"]
        },
        room=other
    )


@socketio.on("webrtc_offer")
def webrtc_offer(data):

    emit(
        "webrtc_offer",
        data,
        room=data.get("receiver")
    )


@socketio.on("webrtc_answer")
def webrtc_answer(data):

    emit(
        "webrtc_answer",
        data,
        room=data.get("receiver")
    )


@socketio.on("ice_candidate")
def ice_candidate(data):

    emit(
        "ice_candidate",
        data,
        room=data.get("receiver")
    )
# ======================================================
# STEP 11
# NOTIFICATION + PIN CHAT + ARCHIVE CHAT
# ======================================================

@socketio.on("notification")
def notification(data):

    if "user" not in session:
        return

    receiver = data.get("receiver")

    emit(
        "notification",
        {
            "title": data.get("title"),
            "body": data.get("body"),
            "sender": session["user"]
        },
        room=receiver
    )


@app.route("/api/pin_chat", methods=["POST"])
def pin_chat():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pinned_chats(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        friend TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO pinned_chats(username,friend)
    VALUES(?,?)
    """,(
        session["user"],
        data["friend"]
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)


@app.route("/api/archive_chat", methods=["POST"])
def archive_chat():

    if "user" not in session:
        return jsonify(success=False),401

    data=request.get_json()

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS archive_chat(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        friend TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO archive_chat(username,friend)
    VALUES(?,?)
    """,(
        session["user"],
        data["friend"]
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)
# ======================================================
# STEP 12
# ONLINE / OFFLINE + LAST SEEN
# ======================================================

active_users = set()


@socketio.on("connect")
def handle_connect():
    if "user" not in session:
        return

    username = session["user"]

    active_users.add(username)

    join_room(username)

    emit(
        "user_status",
        {
            "username": username,
            "online": True
        },
        broadcast=True
    )


@socketio.on("disconnect")
def handle_disconnect():

    if "user" not in session:
        return

    username = session["user"]

    if username in active_users:
        active_users.remove(username)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET last_seen=?
        WHERE username=?
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        username
    ))

    conn.commit()
    conn.close()

    emit(
        "user_status",
        {
            "username": username,
            "online": False
        },
        broadcast=True
    )


@app.route("/api/online_users")
def online_users():

    return jsonify({
        "users": list(active_users)
    })
# ======================================================
# STEP 13
# TYPING + DELIVERY STATUS
# ======================================================

typing_users = {}


@socketio.on("typing_start")
def typing_start(data):

    if "user" not in session:
        return

    receiver = data.get("receiver")

    typing_users[session["user"]] = receiver

    emit(
        "typing_start",
        {
            "sender": session["user"]
        },
        room=receiver,
        include_self=False
    )


@socketio.on("typing_stop")
def typing_stop(data):

    if "user" not in session:
        return

    receiver = data.get("receiver")

    typing_users.pop(session["user"], None)

    emit(
        "typing_stop",
        {
            "sender": session["user"]
        },
        room=receiver,
        include_self=False
    )


@socketio.on("message_delivered")
def message_delivered(data):

    message_id = data.get("message_id")

    if not message_id:
        return

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        ALTER TABLE messages
        ADD COLUMN delivered INTEGER DEFAULT 0
    """)

    conn.commit()

    cursor.execute("""
        UPDATE messages
        SET delivered=1
        WHERE id=?
    """, (message_id,))

    conn.commit()

    cursor.execute("""
        SELECT sender
        FROM messages
        WHERE id=?
    """, (message_id,))

    row = cursor.fetchone()

    conn.close()

    if row:

        emit(
            "message_delivered",
            {
                "message_id": message_id
            },
            room=row["sender"]
        )
# ======================================================
# STEP 14
# FRIEND REQUEST SYSTEM
# ======================================================

@app.route("/api/friend/request", methods=["POST"])
def send_friend_request():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    sender = session["user"]
    receiver = data.get("receiver")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS friend_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        receiver TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO friend_requests(
        sender,
        receiver,
        created_at
    )
    VALUES(?,?,?)
    """,(
        sender,
        receiver,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    socketio.emit(
        "friend_request",
        {
            "sender": sender
        },
        room=receiver
    )

    return jsonify(success=True)


@app.route("/api/friend/accept", methods=["POST"])
def accept_friend_request():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    sender = data.get("sender")
    receiver = session["user"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE friend_requests
    SET status='accepted'
    WHERE sender=? AND receiver=?
    """,(sender,receiver))

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS friends(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1 TEXT,
        user2 TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO friends(user1,user2)
    VALUES(?,?)
    """,(sender,receiver))

    conn.commit()
    conn.close()

    socketio.emit(
        "friend_accepted",
        {
            "user": receiver
        },
        room=sender
    )

    return jsonify(success=True)
# ======================================================
# STEP 15
# GROUP CHAT SYSTEM
# ======================================================

@app.route("/api/group/create", methods=["POST"])
def create_group():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    group_name = data.get("group_name", "").strip()

    if not group_name:
        return jsonify(success=False), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT,
        owner TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_members(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        username TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO groups(
        group_name,
        owner,
        created_at
    )
    VALUES(?,?,?)
    """,(
        group_name,
        session["user"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    group_id = cursor.lastrowid

    cursor.execute("""
    INSERT INTO group_members(
        group_id,
        username
    )
    VALUES(?,?)
    """,(
        group_id,
        session["user"]
    ))

    conn.commit()
    conn.close()

    return jsonify(
        success=True,
        group_id=group_id
    )


@app.route("/api/group/join", methods=["POST"])
def join_group():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    group_id = data.get("group_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO group_members(
        group_id,
        username
    )
    VALUES(?,?)
    """,(
        group_id,
        session["user"]
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)


@socketio.on("group_message")
def group_message(data):

    if "user" not in session:
        return

    emit(
        "group_message",
        {
            "group_id": data.get("group_id"),
            "sender": session["user"],
            "message": data.get("message")
        },
        room=f"group_{data.get('group_id')}",
        broadcast=True
    )
# ======================================================
# STEP 16
# GROUP ADMIN + REMOVE MEMBER + LEAVE GROUP
# ======================================================

@app.route("/api/group/leave", methods=["POST"])
def leave_group():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    group_id = data.get("group_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM group_members
        WHERE group_id=? AND username=?
    """, (
        group_id,
        session["user"]
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)


@app.route("/api/group/remove", methods=["POST"])
def remove_member():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    group_id = data.get("group_id")
    username = data.get("username")

    conn = get_db()
    cursor = conn.cursor()

    owner = cursor.execute("""
        SELECT owner
        FROM groups
        WHERE id=?
    """, (group_id,)).fetchone()

    if not owner or owner["owner"] != session["user"]:
        conn.close()
        return jsonify(success=False), 403

    cursor.execute("""
        DELETE FROM group_members
        WHERE group_id=? AND username=?
    """, (
        group_id,
        username
    ))

    conn.commit()
    conn.close()

    socketio.emit(
        "group_member_removed",
        {
            "group_id": group_id,
            "username": username
        },
        room=f"group_{group_id}"
    )

    return jsonify(success=True)


@app.route("/api/group/members/<int:group_id>")
def group_members(group_id):

    conn = get_db()

    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT username
        FROM group_members
        WHERE group_id=?
    """, (group_id,)).fetchall()

    conn.close()

    return jsonify([
        r["username"]
        for r in rows
    ])
# ======================================================
# STEP 17
# VOICE MESSAGE SYSTEM
# ======================================================

@app.route("/api/upload_voice", methods=["POST"])
def upload_voice():

    if "user" not in session:
        return jsonify(success=False), 401

    if "voice" not in request.files:
        return jsonify(success=False), 400

    voice = request.files["voice"]

    filename = (
        str(uuid.uuid4())
        + ".webm"
    )

    path = os.path.join(
        "static",
        "voice",
        filename
    )

    os.makedirs(
        os.path.dirname(path),
        exist_ok=True
    )

    voice.save(path)

    return jsonify(
        success=True,
        file=filename,
        url="/" + path.replace("\\", "/")
    )


@socketio.on("voice_message")
def voice_message(data):

    if "user" not in session:
        return

    receiver = data.get("receiver")

    socketio.emit(
        "voice_message",
        {
            "sender": session["user"],
            "receiver": receiver,
            "voice": data.get("voice"),
            "time": datetime.now().strftime("%H:%M")
        },
        room=receiver
    )

    socketio.emit(
        "voice_message",
        {
            "sender": session["user"],
            "receiver": receiver,
            "voice": data.get("voice"),
            "time": datetime.now().strftime("%H:%M")
        },
        room=session["user"]
    )
# ======================================================
# STEP 18
# MESSAGE REACTION SYSTEM
# ======================================================

@app.route("/api/message/react", methods=["POST"])
def react_message():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    message_id = data.get("message_id")
    reaction = data.get("reaction")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS message_reactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER,
        username TEXT,
        reaction TEXT
    )
    """)

    cursor.execute("""
    DELETE FROM message_reactions
    WHERE message_id=? AND username=?
    """,(
        message_id,
        session["user"]
    ))

    cursor.execute("""
    INSERT INTO message_reactions(
        message_id,
        username,
        reaction
    )
    VALUES(?,?,?)
    """,(
        message_id,
        session["user"],
        reaction
    ))

    conn.commit()
    conn.close()

    socketio.emit(
        "message_reaction",
        {
            "message_id": message_id,
            "username": session["user"],
            "reaction": reaction
        },
        broadcast=True
    )

    return jsonify(success=True)


@app.route("/api/message/reactions/<int:message_id>")
def get_reactions(message_id):

    conn = get_db()
    cursor = conn.cursor()

    rows = cursor.execute("""
    SELECT username,reaction
    FROM message_reactions
    WHERE message_id=?
    """,(message_id,)).fetchall()

    conn.close()

    return jsonify([
        {
            "username": row["username"],
            "reaction": row["reaction"]
        }
        for row in rows
    ])
# ======================================================
# STEP 19
# LOCATION SHARE + MEDIA PREVIEW
# ======================================================

@app.route("/api/share_location", methods=["POST"])
def share_location():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    socketio.emit(
        "location_message",
        {
            "sender": session["user"],
            "receiver": data.get("receiver"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "time": datetime.now().strftime("%H:%M")
        },
        room=data.get("receiver")
    )

    socketio.emit(
        "location_message",
        {
            "sender": session["user"],
            "receiver": data.get("receiver"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "time": datetime.now().strftime("%H:%M")
        },
        room=session["user"]
    )

    return jsonify(success=True)


@app.route("/api/media_info")
def media_info():

    file = request.args.get("file")

    if not file:
        return jsonify(success=False)

    ext = file.rsplit(".",1)[-1].lower()

    if ext in ["png","jpg","jpeg","gif","webp"]:
        media_type = "image"

    elif ext in ["mp4","webm","mov"]:
        media_type = "video"

    elif ext == "pdf":
        media_type = "pdf"

    else:
        media_type = "file"

    return jsonify(
        success=True,
        type=media_type,
        url=file
    )


@socketio.on("media_preview")
def media_preview(data):

    socketio.emit(
        "media_preview",
        {
            "sender": session["user"],
            "receiver": data.get("receiver"),
            "file": data.get("file")
        },
        room=data.get("receiver")
    )
# ======================================================
# STEP 20
# DELETE & EDIT MESSAGE
# ======================================================

@app.route("/api/message/delete", methods=["POST"])
def delete_message():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    message_id = data.get("message_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM messages
        WHERE id=?
        AND sender=?
    """, (
        message_id,
        session["user"]
    ))

    conn.commit()
    conn.close()

    socketio.emit(
        "message_deleted",
        {
            "message_id": message_id
        },
        broadcast=True
    )

    return jsonify(success=True)


@app.route("/api/message/edit", methods=["POST"])
def edit_message():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    message_id = data.get("message_id")
    new_text = data.get("message")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE messages
        SET message=?
        WHERE id=?
        AND sender=?
    """, (
        new_text,
        message_id,
        session["user"]
    ))

    conn.commit()
    conn.close()

    socketio.emit(
        "message_edited",
        {
            "message_id": message_id,
            "message": new_text
        },
        broadcast=True
    )

    return jsonify(success=True)
# ======================================================
# STEP 21
# BLOCK USER + REPORT USER + PRIVACY
# ======================================================

@app.route("/api/block_user", methods=["POST"])
def block_user():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blocked_users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        blocked_user TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO blocked_users(
        username,
        blocked_user
    )
    VALUES(?,?)
    """,(
        session["user"],
        data["blocked_user"]
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)


@app.route("/api/report_user", methods=["POST"])
def report_user():

    if "user" not in session:
        return jsonify(success=False),401

    data=request.get_json()

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter TEXT,
        reported_user TEXT,
        reason TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO reports(
        reporter,
        reported_user,
        reason,
        created_at
    )
    VALUES(?,?,?,?)
    """,(
        session["user"],
        data["reported_user"],
        data["reason"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)


@app.route("/api/privacy", methods=["POST"])
def privacy():

    if "user" not in session:
        return jsonify(success=False),401

    data=request.get_json()

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS privacy_settings(
        username TEXT PRIMARY KEY,
        last_seen TEXT,
        profile_photo TEXT,
        about TEXT
    )
    """)

    cursor.execute("""
    INSERT OR REPLACE INTO privacy_settings(
        username,
        last_seen,
        profile_photo,
        about
    )
    VALUES(?,?,?,?)
    """,(
        session["user"],
        data.get("last_seen","everyone"),
        data.get("profile_photo","everyone"),
        data.get("about","everyone")
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)
# ======================================================
# STEP 22
# STATUS / STORY SYSTEM
# ======================================================

@app.route("/api/status/upload", methods=["POST"])
def upload_status():

    if "user" not in session:
        return jsonify(success=False), 401

    file = request.files.get("file")

    if not file:
        return jsonify(success=False)

    filename = secure_filename(file.filename)

    ext = filename.rsplit(".", 1)[1].lower()

    new_name = str(uuid.uuid4()) + "." + ext

    folder = os.path.join("static", "status")

    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, new_name)

    file.save(path)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS status(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        file TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO status(
        username,
        file,
        created_at
    )
    VALUES(?,?,?)
    """,(
        session["user"],
        "/static/status/" + new_name,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    socketio.emit(
        "new_status",
        {
            "username": session["user"]
        },
        broadcast=True
    )

    return jsonify(success=True)


@app.route("/api/status/list")
def status_list():

    conn = get_db()
    cursor = conn.cursor()

    rows = cursor.execute("""
    SELECT *
    FROM status
    ORDER BY id DESC
    """).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.route("/api/status/delete", methods=["POST"])
def delete_status():

    if "user" not in session:
        return jsonify(success=False),401

    data = request.get_json()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM status
    WHERE id=?
    AND username=?
    """,(
        data["id"],
        session["user"]
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)
# ======================================================
# STEP 23
# CHANNEL + BROADCAST SYSTEM
# ======================================================

@app.route("/api/channel/create", methods=["POST"])
def create_channel():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS channels(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        owner TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO channels(
        name,
        owner,
        created_at
    )
    VALUES(?,?,?)
    """,(
        data["name"],
        session["user"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)


@app.route("/api/channel/post", methods=["POST"])
def channel_post():

    if "user" not in session:
        return jsonify(success=False),401

    data=request.get_json()

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS channel_posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER,
        message TEXT,
        sender TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    INSERT INTO channel_posts(
        channel_id,
        message,
        sender,
        created_at
    )
    VALUES(?,?,?,?)
    """,(
        data["channel_id"],
        data["message"],
        session["user"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    socketio.emit(
        "channel_post",
        {
            "channel_id":data["channel_id"],
            "message":data["message"],
            "sender":session["user"]
        },
        broadcast=True
    )

    return jsonify(success=True)


@app.route("/api/broadcast", methods=["POST"])
def broadcast_message():

    if "user" not in session:
        return jsonify(success=False),401

    data=request.get_json()

    socketio.emit(
        "broadcast",
        {
            "sender":session["user"],
            "message":data["message"]
        },
        broadcast=True
    )

    return jsonify(success=True)
# ======================================================
# STEP 24
# LOGIN SECURITY + PASSWORD RESET
# ======================================================

import secrets

reset_tokens = {}


@app.route("/api/request_reset", methods=["POST"])
def request_reset():

    data = request.get_json()

    username = data.get("username")

    conn = get_db()
    cursor = conn.cursor()

    user = cursor.execute("""
        SELECT *
        FROM users
        WHERE username=?
    """, (username,)).fetchone()

    conn.close()

    if not user:
        return jsonify(success=False, message="User not found")

    token = secrets.token_hex(32)

    reset_tokens[token] = username

    return jsonify(
        success=True,
        reset_token=token
    )


@app.route("/api/reset_password", methods=["POST"])
def reset_password():

    data = request.get_json()

    token = data.get("token")
    password = data.get("password")

    if token not in reset_tokens:
        return jsonify(success=False)

    username = reset_tokens[token]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET password=?
        WHERE username=?
    """, (
        generate_password_hash(password),
        username
    ))

    conn.commit()
    conn.close()

    del reset_tokens[token]

    return jsonify(success=True)


@app.route("/api/change_password", methods=["POST"])
def change_password():

    if "user" not in session:
        return jsonify(success=False), 401

    data = request.get_json()

    conn = get_db()
    cursor = conn.cursor()

    user = cursor.execute("""
        SELECT password
        FROM users
        WHERE username=?
    """, (session["user"],)).fetchone()

    if not check_password_hash(
        user["password"],
        data["old_password"]
    ):
        conn.close()
        return jsonify(success=False)

    cursor.execute("""
        UPDATE users
        SET password=?
        WHERE username=?
    """, (
        generate_password_hash(data["new_password"]),
        session["user"]
    ))

    conn.commit()
    conn.close()

    return jsonify(success=True)
# ======================================================
# STEP 25
# AUTO DELETE + USER STATS + ADMIN PANEL
# ======================================================

@app.route("/api/admin/stats")
def admin_stats():

    conn = get_db()
    cursor = conn.cursor()

    users = cursor.execute(
        "SELECT COUNT(*) total FROM users"
    ).fetchone()["total"]

    messages = cursor.execute(
        "SELECT COUNT(*) total FROM messages"
    ).fetchone()["total"]

    groups = cursor.execute("""
        SELECT COUNT(*) total
        FROM groups
    """).fetchone()

    groups = groups["total"] if groups else 0

    conn.close()

    return jsonify({
        "users": users,
        "messages": messages,
        "groups": groups
    })


@app.route("/api/admin/users")
def admin_users():

    conn = get_db()

    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT username,last_seen
        FROM users
        ORDER BY username
    """).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.route("/api/admin/delete_user", methods=["POST"])
def admin_delete_user():

    data = request.get_json()

    username = data.get("username")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM users
        WHERE username=?
    """,(username,))

    conn.commit()
    conn.close()

    return jsonify(success=True)


@app.route("/api/message/auto_delete", methods=["POST"])
def auto_delete_message():

    data = request.get_json()

    message_id = data.get("message_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM messages
        WHERE id=?
    """,(message_id,))

    conn.commit()
    conn.close()

    socketio.emit(
        "message_deleted",
        {
            "message_id": message_id
        },
        broadcast=True
    )

    return jsonify(success=True)


@socketio.on("server_ping")
def server_ping():

    emit(
        "server_pong",
        {
            "status":"online",
            "time":datetime.now().strftime("%H:%M:%S")
        }
    )
