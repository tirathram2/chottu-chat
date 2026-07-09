const socket = io();

const myUsername = document.body.dataset.username;

const messages = document.getElementById("messages");

const input = document.getElementById("msg");

socket.on("connect", () => {
    console.log("Connected");
});

function sendMsg() {

    if (input.value.trim() == "") return;

    socket.emit("message", {
        sender: myUsername,
        message: input.value
    });

    input.value = "";
}

socket.on("message", function(data) {

    const li = document.createElement("li");

    if (data.sender === myUsername) {
        li.className = "my-message";
    } else {
        li.className = "other-message";
    }

    li.innerHTML = `
        <b>${data.sender}</b><br>
        ${data.message}
    `;

    messages.appendChild(li);

    messages.scrollTop = messages.scrollHeight;
});

input.addEventListener("input", () => {

    socket.emit("typing", {
        username: myUsername
    });

});

socket.on("typing", function(data) {

    if (data.username === myUsername) return;

    document.getElementById("typing").innerHTML =
        data.username + " is typing...";

    clearTimeout(window.typingTimeout);

    window.typingTimeout = setTimeout(() => {

        document.getElementById("typing").innerHTML = "";

    }, 1000);

});

document.getElementById("voiceCallBtn").onclick = () => {
    alert("Voice Call coming soon");
};

document.getElementById("videoCallBtn").onclick = () => {
    alert("Video Call coming soon");
};
