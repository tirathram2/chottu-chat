from flask import Flask
from flask_socketio import SocketIO, send
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'

socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def home():
    return """
    <h2>Real Time Chat</h2>

    <ul id="messages"></ul>

    <input id="msg" placeholder="Type message">
    <button onclick="sendMsg()">Send</button>

    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <script>
        var socket = io();

        socket.on("message", function(msg){
            var li = document.createElement("li");
            li.textContent = msg;
            document.getElementById("messages").appendChild(li);
        });

        function sendMsg(){
            var msg = document.getElementById("msg").value;
            socket.send(msg);
            document.getElementById("msg").value = "";
        }
    </script>
    """

@socketio.on("message")
def handle_message(msg):
    send(msg, broadcast=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
