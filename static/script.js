var socket = io();

const myUsername = document.body.dataset.username;

socket.on("message", function(data) {

    var li = document.createElement("li");

    if (data.sender === myUsername) {
        li.className = "my-message";
    } else {
        li.className = "other-message";
    }

    li.innerHTML =
        "<b>" + data.sender + "</b><br>" +
        data.message;

    document.getElementById("messages").appendChild(li);

    document.getElementById("messages").scrollTop =
        document.getElementById("messages").scrollHeight;
});

function sendMsg() {

    var input = document.getElementById("msg");

    if (input.value.trim() !== "") {
        socket.send(input.value);
        input.value = "";
    }
}

document.getElementById("voiceCallBtn")?.addEventListener("click", () => {
    alert("📞 Voice Call feature is coming soon...");
});

document.getElementById("videoCallBtn")?.addEventListener("click", () => {
    alert("🎥 Video Call feature is coming soon...");
});
