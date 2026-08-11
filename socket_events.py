"""Socket.IO presence, messaging, typing, and WebRTC signal relay."""
from collections import defaultdict
import sqlite3
from flask import request
from flask_login import current_user
from flask_socketio import SocketIO, emit, join_room
from database import get_db
from upload import valid_attachment_path
from utils import message_json, utc_now
socketio = SocketIO(); _user_sids = defaultdict(set)
def init_socketio(app): socketio.init_app(app, cors_allowed_origins=app.config["CORS_ORIGINS"], async_mode=app.config["SOCKETIO_ASYNC_MODE"])
def is_online(user_id): return bool(_user_sids.get(str(user_id)))
def _recipient(value):
    if value in (None, "", "global"): return None
    try: user_id = int(value)
    except (TypeError, ValueError): return False
    return user_id if user_id > 0 else False
def _user_exists(user_id):
    connection = get_db()
    try: return bool(connection.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone())
    finally: connection.close()
@socketio.on("connect")
def connect(auth=None):
    if not current_user.is_authenticated: return False
    _user_sids[str(current_user.id)].add(request.sid); join_room(f"user:{current_user.id}"); join_room("global")
    emit("presence", {"id":current_user.id,"online":True}, broadcast=True)
@socketio.on("disconnect")
def disconnect():
    if not current_user.is_authenticated: return
    user_id = str(current_user.id); _user_sids[user_id].discard(request.sid)
    if _user_sids[user_id]: return
    _user_sids.pop(user_id, None); connection = get_db()
    try: connection.execute("UPDATE users SET last_seen = ? WHERE id = ?", (utc_now(), current_user.id)); connection.commit()
    finally: connection.close()
    emit("presence", {"id":current_user.id,"online":False}, broadcast=True)
@socketio.on("typing")
def typing(data):
    recipient_id = _recipient((data or {}).get("recipient_id"))
    if recipient_id is False or (recipient_id is not None and not _user_exists(recipient_id)): return
    emit("typing", {"sender_id":current_user.id,"typing":bool((data or {}).get("typing"))}, to="global" if recipient_id is None else f"user:{recipient_id}", include_self=False)
@socketio.on("send_message")
def send_message(data):
    if not current_user.is_authenticated or not isinstance(data, dict): return
    body, recipient_id, attachment = str(data.get("body") or "").strip()[:4000], _recipient(data.get("recipient_id")), data.get("attachment")
    attachment_type = data.get("attachment_type")
    if recipient_id is False or recipient_id == current_user.id: emit("message_error", {"error":"Choose another user for a private chat."}); return
    if recipient_id is not None and not _user_exists(recipient_id): emit("message_error", {"error":"Recipient not found."}); return
    if attachment and not valid_attachment_path(attachment): emit("message_error", {"error":"Invalid attachment."}); return
    if attachment_type not in {None,"image","video","pdf"}: attachment_type = None
    if not body and not attachment: return
    connection = get_db()
    try:
        cursor = connection.execute("INSERT INTO messages (sender_id, recipient_id, body, attachment, attachment_type, created_at) VALUES (?, ?, ?, ?, ?, ?)", (current_user.id,recipient_id,body,attachment,attachment_type,utc_now())); connection.commit()
        row = connection.execute("SELECT m.*, u.username sender_name, u.avatar sender_avatar FROM messages m JOIN users u ON u.id = m.sender_id WHERE m.id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.Error:
        connection.rollback()
        emit("message_error", {"error":"Message could not be saved."})
        return {"ok": False, "error": "Message could not be saved."}
    finally: connection.close()
    message = message_json(row)
    emit("new_message", message, to="global" if recipient_id is None else f"user:{recipient_id}")
    if recipient_id is not None: emit("new_message", message, to=f"user:{current_user.id}")
    return {"ok": True, "message": message}
@socketio.on("mark_seen")
def mark_seen(data):
    peer_id = _recipient((data or {}).get("peer_id"))
    if peer_id in (None,False) or peer_id == current_user.id: return
    connection = get_db()
    try: connection.execute("UPDATE messages SET seen_at = ? WHERE sender_id = ? AND recipient_id = ? AND seen_at IS NULL", (utc_now(),peer_id,current_user.id)); connection.commit()
    finally: connection.close()
    emit("seen", {"by":current_user.id}, to=f"user:{peer_id}")
def _relay_signal(event, data):
    data = data if isinstance(data,dict) else {}; recipient_id = _recipient(data.get("recipient_id"))
    if recipient_id in (None,False) or recipient_id == current_user.id or not _user_exists(recipient_id): return
    payload = {key:value for key,value in data.items() if key != "sender_id"}; payload["sender_id"] = current_user.id
    emit(event, payload, to=f"user:{recipient_id}")
for _event in ("call_signal","accept_call","reject_call","end_call","ice_candidate","offer","answer"):
    socketio.on_event(_event, lambda data, event=_event: _relay_signal(event,data))
