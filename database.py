"""SQLite persistence and models. Existing databases are upgraded in place."""
import sqlite3
from flask import current_app
from flask_login import UserMixin

def get_db():
    connection = sqlite3.connect(current_app.config["DATABASE_PATH"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

class User(UserMixin):
    def __init__(self, row):
        self.id, self.username, self.password = row["id"], row["username"], row["password"]
        self.email = row["email"] if "email" in row.keys() else None
        self.avatar, self.bio, self.last_seen = row["avatar"], row["bio"] or "", row["last_seen"]

def get_user(user_id):
    connection = get_db()
    try:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return User(row) if row else None
    finally: connection.close()

def init_db(app):
    app.config["DATABASE_PATH"].parent.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        connection.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, avatar TEXT, bio TEXT DEFAULT '', last_seen TEXT, created_at TEXT NOT NULL, email TEXT);
        CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER NOT NULL, recipient_id INTEGER, body TEXT, attachment TEXT, attachment_type TEXT, created_at TEXT NOT NULL, seen_at TEXT, FOREIGN KEY(sender_id) REFERENCES users(id), FOREIGN KEY(recipient_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS contacts (user_id INTEGER NOT NULL, contact_id INTEGER NOT NULL, PRIMARY KEY(user_id, contact_id));
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        if "email" not in columns: connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users(email) WHERE email IS NOT NULL")
        connection.execute("CREATE INDEX IF NOT EXISTS messages_private_lookup ON messages(sender_id, recipient_id, id)")
        connection.execute("CREATE INDEX IF NOT EXISTS messages_global_lookup ON messages(recipient_id, id)")
        connection.commit()
    finally: connection.close()
