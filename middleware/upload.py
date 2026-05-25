import os
import uuid
from fastapi import File, UploadFile
from fastapi.exceptions import HTTPException
from pathlib import Path

# 允许的 MIME 类型白名单
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
# 允许的扩展名白名单
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
# 最大文件大小（字节），默认 5MB
MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_MB", "5")) * 1024 * 1024

UPLOAD_DIR = Path(__file__).parent.parent / "uploads" / "pets"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def validate_file(file: UploadFile):
    """校验上传文件：类型 + 大小"""
    # 1. 扩展名 & MIME 校验
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if file.content_type not in ALLOWED_MIMES or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=1001,
            detail="仅支持 JPG/PNG/WebP/GIF 格式的图片"
        )

    # 2. 文件大小校验（需先读取内容才能拿到大小）
    #    这里仅预检 content_length header（客户端可能不提供）
    #    真正的大小校验在 save_file 中读取后完成
    return True


def save_file(file: UploadFile) -> str:
    """保存文件，同时校验大小"""
    content = file.file.read()

    # 文件大小校验
    if len(content) > MAX_FILE_SIZE:
        size_mb = MAX_FILE_SIZE // (1024 * 1024)
        raise HTTPException(
            status_code=1001,
            detail=f"文件大小超过限制（最大 {size_mb}MB）"
        )

    # 文件头魔数校验
    MAGIC_NUMBERS = {
        b'\xff\xd8\xff': 'jpeg',
        b'\x89PNG': 'png',
        b'GIF8': 'gif',
        b'RIFF': 'webp',  # WebP 文件以 RIFF 开头
    }
    is_valid_image = False
    for magic, fmt in MAGIC_NUMBERS.items():
        if content[:len(magic)] == magic:
            is_valid_image = True
            break
    if not is_valid_image:
        raise HTTPException(status_code=1001, detail="文件内容与扩展名不匹配，疑似伪造文件")

    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as buffer:
        buffer.write(content)
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
