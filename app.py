
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, send
import sqlite3
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret"
app.config["PERMANENT_SESSION_LIFETIME"] = 86400
DATABASE = "users.db"


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        online INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT NOT NULL,
        receiver TEXT NOT NULL,
        message TEXT NOT NULL,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

socketio = SocketIO(app, cors_allowed_origins="*")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )

        user = cursor.fetchone()

        if user:
            cursor.execute(
                "UPDATE users SET online=1 WHERE username=?",
                (username,)
            )
            conn.commit()
            conn.close()

            session["username"] = username

            return redirect(url_for("chat"))

        conn.close()
        return "Invalid username or password"

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, password)
            )
            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return "This email or username is already registered."

        conn.close()
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/chat")
def chat():
    if "username" not in session:
        return redirect(url_for("login"))

    return render_template("index.html", username=session["username"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
@app.route("/users")
def users():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT username, online FROM users WHERE username != ?",
        (session["username"],)
    )

    users = cursor.fetchall()
    conn.close()

    return {
        "users": [
            {"username": u[0], "online": u[1]}
            for u in users
        ]
    } 
@app.route("/messages/<username>")
def get_messages(username):

    if "username" not in session:
        return {"messages": []}

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT sender, receiver, message
    FROM messages
    WHERE
        (sender=? AND receiver=?)
        OR
        (sender=? AND receiver=?)
    ORDER BY id
    """, (
        session["username"],
        username,
        username,
        session["username"]
    ))

    rows = cursor.fetchall()
    conn.close()

    return {
        "messages": [
            {
                "sender": row[0],
                "receiver": row[1],
                "message": row[2]
            }
            for row in rows
        ]
    }    
@socketio.on("message")
def handle_message(msg):
    send(msg, broadcast=True)
@socketio.on("call-user")
def call_user(data):
    socketio.emit("incoming-call", data, broadcast=True)
@socketio.on("private-message")
def private_message(data):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO messages (sender, receiver, message) VALUES (?, ?, ?)",
        (
            session["username"],
            data["to"],
            data["message"]
        )
    )

    conn.commit()
    conn.close()

    socketio.emit("private-message", {
        "from": session["username"],
        "to": data["to"],
        "message": data["message"]
    })
@socketio.on("user-online")
def user_online(username):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET online=1 WHERE username=?",
        (username,)
    )

    conn.commit()
    conn.close()

    socketio.emit("refresh-users")
 @socketio.on("user-offline")
def user_offline(username):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET online=0 WHERE username=?",
        (username,)
    )

    conn.commit()
    conn.close()

    socketio.emit("refresh-users")   
@socketio.on("answer-call")
def answer_call(data):
    socketio.emit("call-answered", data, broadcast=True)


@socketio.on("ice-candidate")
def ice_candidate(data):
    socketio.emit("ice-candidate", data, broadcast=True)

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)

