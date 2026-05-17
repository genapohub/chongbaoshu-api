import os
import uuid
from fastapi import File, UploadFile
from fastapi.exceptions import HTTPException
from pathlib import Path

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

UPLOAD_DIR = Path(__file__).parent.parent / "uploads" / "pets"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def validate_file(file: UploadFile):
    ext = Path(file.filename).suffix.lower()
    if file.content_type not in ALLOWED_MIMES or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WebP/GIF 格式的图片")
    return True

def save_file(file: UploadFile) -> str:
    ext = Path(file.filename).suffix.lower()
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())
    return f"/uploads/pets/{filename}"

def delete_local_file(photo_url: str):
    try:
        if not photo_url or not photo_url.startswith("/uploads/"):
            return
        file_path = Path(__file__).parent.parent / photo_url.lstrip("/")
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        print(f"[删除文件失败] {photo_url} {str(e)}")
