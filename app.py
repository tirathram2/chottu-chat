from flask import Flask, request, redirect
import sqlite3

app = Flask(__name__)

# Database তৈরি
conn = sqlite3.connect("chat.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT
)
""")
conn.commit()

@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":
        msg = request.form["msg"]

        if msg.strip():
            cur.execute(
                "INSERT INTO messages(text) VALUES(?)",
                (msg,)
            )
            conn.commit()

        return redirect("/")

    cur.execute("SELECT text FROM messages")
    messages = cur.fetchall()

    html = """
    <html>
    <head>
    <title>Chottu Chat</title>
    <style>
    body{
        background:#e5ddd5;
        font-family:Arial;
        margin:0;
    }

    .header{
        background:#075e54;
        color:white;
        padding:15px;
        text-align:center;
        font-size:24px;
    }

    .chat{
        padding:15px;
        margin-bottom:80px;
    }

    .msg{
        background:white;
        padding:10px;
        margin:10px;
        border-radius:10px;
        width:fit-content;
        max-width:70%;
    }

    .bottom{
        position:fixed;
        bottom:0;
        width:100%;
        background:white;
        padding:10px;
    }

    input{
        width:75%;
        padding:10px;
    }

    button{
        padding:10px 20px;
    }
    </style>
    </head>
    <body>

    <div class="header">Chottu Chat</div>

    <div class="chat">
    """

    for m in messages:
        html += f"<div class='msg'>{m[0]}</div>"

    html += """
    </div>

    <div class="bottom">
    <form method="POST">
        <input type="text" name="msg" placeholder="Type message...">
        <button type="submit">Send</button>
    </form>
    </div>

    </body>
    </html>
    """

    return html

if __name__ == "__main__":
    app.run(debug=True)