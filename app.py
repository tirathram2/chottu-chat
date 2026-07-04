
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, send
import sqlite3
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret"

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
    return render_template("index.html")


@socketio.on("message")
def handle_message(msg):
    send(msg, broadcast=True)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
=======
    socketio.run(app, host="0.0.0.0", port=port)

>>>>>>> d6e18af9097116c37d6ca12e2a55b85da1232235
