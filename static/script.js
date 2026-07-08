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
let localStream = null;

async function startLocalMedia(video = true) {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({
            video: video,
            audio: true
        });

        document.getElementById("callWindow").style.display = "block";
        document.getElementById("localVideo").srcObject = localStream;

    } catch (err) {
        alert("Camera/Microphone permission denied.");
        console.error(err);
    }
}

document.getElementById("voiceCallBtn").addEventListener("click", async () => {
    await startLocalMedia(false);
});

document.getElementById("videoCallBtn").addEventListener("click", async () => {
    await startLocalMedia(true);
});

document.getElementById("endCallBtn").addEventListener("click", () => {

    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
    }

    document.getElementById("callWindow").style.display = "none";
});
async function loadUsers() {

    const response = await fetch("/users");
    const data = await response.json();

    const userList = document.getElementById("userList");

    data.users.forEach(user => {

        const div = document.createElement("div");

        div.className = "chat-item";

        div.innerHTML = `
            <img src="https://i.imgur.com/6VBx3io.png">
            <div>
                <h4>${user.username}</h4>
                <p>${user.online ? "🟢 Online" : "⚪ Offline"}</p>
            </div>
        `;

        userList.appendChild(div);

    });

}

loadUsers();
socket.on("private-message", function(data) {

    if (
        data.from === selectedUser ||
        data.to === selectedUser
    ) {

        var li = document.createElement("li");

        li.innerText = data.from + ": " + data.message;

        document.getElementById("messages").appendChild(li);
    }

});
async function loadMessages(username) {

    const response = await fetch("/messages/" + username);
    const data = await response.json();

    const messages = document.getElementById("messages");
    messages.innerHTML = "";

    data.messages.forEach(msg => {

        const li = document.createElement("li");

        li.innerText = msg.sender + ": " + msg.message;

        messages.appendChild(li);

    });

}
socket.on("refresh-users", () => {

    document.getElementById("userList").innerHTML = "";

    loadUsers();

});
socket.on("seen", function(data) {
    console.log(data.from + " has seen your message");
});
