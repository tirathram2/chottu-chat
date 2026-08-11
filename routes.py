"""Authenticated HTTP routes and JSON APIs."""
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from database import get_db
from socket_events import is_online
from upload import IMAGE_EXTENSIONS, save_upload
from utils import message_json, user_json, utc_now
routes_bp = Blueprint("routes", __name__)

@routes_bp.get("/")
def home(): return render_template("index.html") if current_user.is_authenticated else redirect(url_for("auth.login"))
@routes_bp.get("/api/me")
@login_required
def me(): return jsonify({"id":current_user.id,"username":current_user.username,"avatar":url_for("static", filename=current_user.avatar or "default.png"),"bio":current_user.bio})
@routes_bp.get("/api/users")
@login_required
def users():
    query = request.args.get("q", "").strip().lower()[:64]; connection = get_db()
    try: rows = connection.execute("SELECT * FROM users WHERE id != ? AND username LIKE ? ORDER BY username LIMIT 30", (current_user.id, f"%{query}%")).fetchall()
    finally: connection.close()
    return jsonify([user_json(row, is_online(row["id"])) for row in rows])
@routes_bp.post("/api/profile")
@login_required
def profile():
    bio, avatar = request.form.get("bio", "").strip()[:180], current_user.avatar; avatar_file = request.files.get("avatar")
    if avatar_file and avatar_file.filename:
        if "." not in avatar_file.filename or avatar_file.filename.rsplit(".", 1)[1].lower() not in IMAGE_EXTENSIONS: return jsonify(error="Please choose an image file."), 400
        try: avatar, _category = save_upload(avatar_file, directory="avatars")
        except ValueError as error: return jsonify(error=str(error)), 400
    connection = get_db()
    try: connection.execute("UPDATE users SET bio = ?, avatar = ? WHERE id = ?", (bio, avatar, current_user.id)); connection.commit()
    finally: connection.close()
    return jsonify(ok=True, avatar=url_for("static", filename=avatar or "default.png"))
def _messages(where, parameters):
    connection = get_db()
    try:
        rows = connection.execute("SELECT m.*, u.username sender_name, u.avatar sender_avatar FROM messages m JOIN users u ON u.id = m.sender_id WHERE " + where + " ORDER BY m.id DESC LIMIT 100", parameters).fetchall()
        return [message_json(row) for row in reversed(rows)]
    finally: connection.close()
@routes_bp.get("/api/messages/<int:peer_id>")
@login_required
def private_messages(peer_id):
    if peer_id == current_user.id: return jsonify(error="A private chat needs another user."), 400
    connection = get_db()
    try:
        if not connection.execute("SELECT 1 FROM users WHERE id = ?", (peer_id,)).fetchone(): return jsonify(error="User not found."), 404
        connection.execute("UPDATE messages SET seen_at = ? WHERE sender_id = ? AND recipient_id = ? AND seen_at IS NULL", (utc_now(), peer_id, current_user.id)); connection.commit()
    finally: connection.close()
    return jsonify(_messages("(m.sender_id = ? AND m.recipient_id = ?) OR (m.sender_id = ? AND m.recipient_id = ?)", (current_user.id, peer_id, peer_id, current_user.id)))
@routes_bp.get("/api/messages/global")
@login_required
def global_messages(): return jsonify(_messages("m.recipient_id IS NULL", ()))
@routes_bp.get("/api/search")
@login_required
def search_messages():
    query = request.args.get("q", "").strip()[:100]
    if not query: return jsonify([])
    return jsonify(_messages("m.body LIKE ? AND (m.recipient_id IS NULL OR m.sender_id = ? OR m.recipient_id = ?)", (f"%{query}%", current_user.id, current_user.id)))
@routes_bp.post("/api/upload")
@login_required
def upload():
    try: relative, category = save_upload(request.files.get("file"))
    except ValueError as error: return jsonify(error=str(error)), 400
    return jsonify(path=relative, url=url_for("static", filename=relative), type=category)
