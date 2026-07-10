from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO
import sqlite3
import os

app = Flask(__name__)

app.config["SECRET_KEY"] = "chottu_secret_key"
app.config["PERMANENT_SESSION_LIFETIME"] = 86400

DATABASE = "users.db"

socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        username TEXT UNIQUE NOT NULL,

        email TEXT UNIQUE NOT NULL,

        password TEXT NOT NULL,

        profile TEXT DEFAULT 'default.png',

        online INTEGER DEFAULT 0

    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        sender TEXT NOT NULL,

        receiver TEXT NOT NULL,

        message TEXT NOT NULL,

        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        seen INTEGER DEFAULT 0

    )
    """)

    conn.commit()

    conn.close()
