var socket = io();

socket.on("message", function(msg) {
    var li = document.createElement("li");
    li.innerText = msg;
    document.getElementById("messages").appendChild(li);
});

function sendMsg() {
    var input = document.getElementById("msg");

    if (input.value.trim() !== "") {
        socket.send(input.value);
        input.value = "";
    }
}
document.getElementById("voiceCallBtn").addEventListener("click", () => {
    alert("📞 Voice Call feature is coming soon...");
});

document.getElementById("videoCallBtn").addEventListener("click", () => {
    alert("🎥 Video Call feature is coming soon...");
});
socket.on("incoming-call", (data) => {
    alert("📞 Incoming Call from: " + data.from);
});

socket.on("call-answered", () => {
    alert("✅ Call Accepted");
});

document.getElementById("voiceCallBtn").onclick = () => {
    socket.emit("call-user", {
        from: "User"
    });
};

document.getElementById("videoCallBtn").onclick = () => {
    socket.emit("call-user", {
        from: "User (Video)"
    });
};
