from flask import Flask, render_template, redirect, url_for
from flask_socketio import SocketIO, send
import os
import sqlite3

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet"
)

# Home Page
@app.route("/")
def home():
    return render_template("index.html")


# Login Page
@app.route("/login")
def login():
    return render_template("login.html")


# Signup Page
@app.route("/signup")
def signup():
    return render_template("signup.html")


# Optional Redirect
@app.route("/chat")
def chat():
    return redirect(url_for("home"))


# Chat Message
@socketio.on("message")
def handle_message(msg):
    send(msg, broadcast=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
