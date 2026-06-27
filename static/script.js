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
