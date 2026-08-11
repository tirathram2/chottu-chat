"""Validated, non-traversable file upload handling."""
from pathlib import Path
from uuid import uuid4
from flask import current_app
from werkzeug.utils import secure_filename
IMAGE_EXTENSIONS, VIDEO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}, {"mp4", "webm"}
def allowed_file(filename): return bool(filename and "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"])
def save_upload(file, directory="uploads"):
    if not file or not file.filename or not allowed_file(file.filename): raise ValueError("Allowed file types: images, videos, and PDF files.")
    original = secure_filename(file.filename)
    if not original: raise ValueError("Choose a valid filename.")
    extension, relative = original.rsplit(".", 1)[1].lower(), f"{directory}/{uuid4().hex}_{original}"
    static_root = Path(current_app.config["UPLOAD_FOLDER"]).parent.resolve(); target = (static_root / relative).resolve()
    if static_root not in target.parents: raise ValueError("Invalid upload path.")
    target.parent.mkdir(parents=True, exist_ok=True); file.save(target)
    return relative, ("image" if extension in IMAGE_EXTENSIONS else "video" if extension in VIDEO_EXTENSIONS else "pdf")
def valid_attachment_path(path):
    if not isinstance(path, str) or not path.startswith("uploads/"): return False
    candidate = (Path(current_app.config["UPLOAD_FOLDER"]).parent / path).resolve(); root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    return root in candidate.parents and candidate.is_file()
