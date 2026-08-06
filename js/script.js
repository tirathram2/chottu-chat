const socket = io();

let currentReceiver = null;

const messages = document.getElementById("messages");
const input = document.getElementById("msg");
const typingBox = document.getElementById("typing");

socket.on("connect", () => {
    console.log("Connected");
});

function addMessage(data) {

    const li = document.createElement("li");

    if (window.currentUser && data.sender_id == window.currentUser.id) {
        li.className = "my-message";
    } else {
        li.className = "other-message";
    }

    li.innerHTML = `
        <div class="name">${data.sender_name}</div>
        <div class="text">${data.content}</div>
    `;

    messages.appendChild(li);

    messages.scrollTop = messages.scrollHeight;
}

function sendMsg() {

    const text = input.value.trim();

    if (text === "") return;

    socket.emit("send_message", {
        receiver_id: currentReceiver,
        content: text,
        message_type: "text"
    });

    input.value = "";
}

socket.on("new_message", function(data) {

    addMessage(data);

});

input.addEventListener("input", () => {

    socket.emit("typing", {
        receiver_id: currentReceiver,
        is_typing: true
    });

});

socket.on("typing", function(data) {

    typingBox.innerHTML =
        data.name + " is typing...";

    clearTimeout(window.typingTimer);

    window.typingTimer = setTimeout(() => {

        typingBox.innerHTML = "";

    },1000);

});

async function loadMe(){

    const res = await fetch("/api/me");

    if(!res.ok) return;

    const data = await res.json();

    window.currentUser = data.user;

}

async function loadGlobalMessages(){

    const res = await fetch("/api/messages/global");

    const data = await res.json();

    messages.innerHTML = "";

    data.messages.forEach(addMessage);

}

window.onload = async function(){

    await loadMe();

    await loadGlobalMessages();

}

document.getElementById("voiceCallBtn")?.addEventListener("click",()=>{

    alert("Voice Call Coming Soon");

});

document.getElementById("videoCallBtn")?.addEventListener("click",()=>{

    alert("Video Call Coming Soon");

});
