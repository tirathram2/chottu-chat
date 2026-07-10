const socket = io();

const myUsername = document.body.dataset.username;

const messages = document.getElementById("messages");
const input = document.getElementById("msg");
const typing = document.getElementById("typing");

// Connect
socket.on("connect", () => {
    console.log("Connected");
});

// Send Message
function sendMsg() {

    const text = input.value.trim();

    if (text === "") return;

    socket.emit("message", {
        sender: myUsername,
        message: text
    });

    input.value = "";
}

// Press Enter
input.addEventListener("keypress", function(e) {

    if (e.key === "Enter") {
        sendMsg();
    }

});

// Receive Message
socket.on("message", function(data) {

    const li = document.createElement("li");

    li.className =
        data.sender === myUsername
            ? "my-message"
            : "other-message";

    li.innerHTML = `
        <div class="name">${data.sender}</div>
        <div class="text">${data.message}</div>
    `;

    messages.appendChild(li);

    messages.scrollTop = messages.scrollHeight;

});

// Typing
input.addEventListener("input", () => {

    socket.emit("typing", {
        username: myUsername
    });

});

// Receive Typing
socket.on("typing", function(data) {

    if (data.username === myUsername) return;

    typing.innerHTML =
        data.username + " is typing...";

    clearTimeout(window.typingTimer);

    window.typingTimer = setTimeout(() => {

        typing.innerHTML = "";

    }, 1000);

});

// Voice Call Button
document.getElementById("voiceCallBtn").onclick = () => {

    alert("Voice Call Coming Soon");

};

// Video Call Button
document.getElementById("videoCallBtn").onclick = () => {

    alert("Video Call Coming Soon");

};
