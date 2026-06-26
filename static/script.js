var socket = io(); socket.on("message", function(msg){ var li = document.createElement("li"); li.innerText = msg; document.getElementById("messages").appendChild(li);
