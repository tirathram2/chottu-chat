"""Shared validation, serialization, and timestamp helpers."""
from datetime import datetime, timezone
import re
from flask import url_for
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
def utc_now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def normalize_username(value): return (value or "").strip().lower()
def normalize_email(value): return (value or "").strip().lower()
def valid_username(value): return bool(USERNAME_RE.fullmatch(value))
def valid_email(value): return bool(EMAIL_RE.fullmatch(value)) and len(value) <= 254
def static_url(filename): return url_for("static", filename=filename or "default.png")
def user_json(row, online=False): return {"id":row["id"],"username":row["username"],"avatar":static_url(row["avatar"]),"bio":row["bio"] or "","online":online,"last_seen":row["last_seen"]}
def message_json(row): return {"id":row["id"],"sender_id":row["sender_id"],"recipient_id":row["recipient_id"],"body":row["body"] or "","attachment":static_url(row["attachment"]) if row["attachment"] else None,"attachment_type":row["attachment_type"],"created_at":row["created_at"],"seen":bool(row["seen_at"]),"sender_name":row["sender_name"],"sender_avatar":static_url(row["sender_avatar"])}
