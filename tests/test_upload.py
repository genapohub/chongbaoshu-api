"""
文件上传校验测试
- 类型校验（非法 MIME / 扩展名）
- 大小校验（超过 5MB）
"""
import pytest
from io import BytesIO
from unittest.mock import MagicMock


def make_upload_file(filename: str, content: bytes, content_type: str = "image/jpeg"):
    """辅助：构造 UploadFile mock 对象"""
    f = MagicMock()
    f.filename = filename
    f.content_type = content_type
    f.file = BytesIO(content)
    f.read = f.file.read
    return f


class TestUploadValidation:
    """middleware/upload.py 校验逻辑"""

    def test_validate_allowed_jpeg(self):
        from middleware.upload import validate_file
        f = make_upload_file("photo.jpg", b"\xff\xd8\xff", "image/jpeg")
        assert validate_file(f) is True

    def test_validate_allowed_png(self):
        from middleware.upload import validate_file
        f = make_upload_file("photo.png", b"\x89PNG", "image/png")
        assert validate_file(f) is True

    def test_validate_disallowed_type(self):
        from middleware.upload import validate_file
        from fastapi.exceptions import HTTPException
        f = make_upload_file("doc.pdf", b"%PDF", "application/pdf")
        with pytest.raises(HTTPException) as exc_info:
            validate_file(f)
        assert exc_info.value.status_code == 1001

    def test_validate_disallowed_extension(self):
        from middleware.upload import validate_file
        from fastapi.exceptions import HTTPException
        # MIME 是 image/jpeg 但扩展名是 .exe
        f = make_upload_file("malware.exe", b"MZ", "image/jpeg")
        with pytest.raises(HTTPException):
            validate_file(f)

    def test_save_file_size_exceeded(self):
        from middleware.upload import save_file, MAX_FILE_SIZE
        from fastapi.exceptions import HTTPException
        big_content = b"\x00" * (MAX_FILE_SIZE + 1)
        f = make_upload_file("big.jpg", big_content, "image/jpeg")
        with pytest.raises(HTTPException) as exc_info:
            save_file(f)
        assert exc_info.value.status_code == 1001
        assert "超过限制" in exc_info.value.detail

    def test_save_file_within_limit(self):
        from middleware.upload import save_file
        import os
        small_content = b"\xff\xd8\xff\xe0" + b"\x00" * 1024
        f = make_upload_file("small.jpg", small_content, "image/jpeg")
        result = save_file(f)
        assert result.startswith("/uploads/pets/")
        file_path = "." + result
        if os.path.exists(file_path):
            os.remove(file_path)


class TestMagicNumberValidation:
    """文件头魔数校验"""

    def test_save_jpeg_magic_valid(self):
        """JPEG 魔数正确应通过"""
        from middleware.upload import save_file
        import os
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 1024
        f = make_upload_file("photo.jpg", content, "image/jpeg")
        result = save_file(f)
        assert result.startswith("/uploads/pets/")
        file_path = "." + result
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_save_png_magic_valid(self):
        """PNG 魔数正确应通过"""
        from middleware.upload import save_file
        import os
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024
        f = make_upload_file("photo.png", content, "image/png")
        result = save_file(f)
        assert result.startswith("/uploads/pets/")
        file_path = "." + result
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_save_gif_magic_valid(self):
        """GIF 魔数正确应通过"""
        from middleware.upload import save_file
        import os
        content = b"GIF89a" + b"\x00" * 1024
        f = make_upload_file("photo.gif", content, "image/gif")
        result = save_file(f)
        assert result.startswith("/uploads/pets/")
        file_path = "." + result
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_save_webp_magic_valid(self):
        """WebP 魔数正确应通过（RIFF 开头）"""
        from middleware.upload import save_file
        import os
        content = b"RIFF" + b"\x00" * 1024
        f = make_upload_file("photo.webp", content, "image/webp")
        result = save_file(f)
        assert result.startswith("/uploads/pets/")
        file_path = "." + result
        if os.path.exists(file_path):
            os.remove(file_path)

    def test_save_fake_image_rejected(self):
        """伪造图片（魔数不匹配）应被拒绝"""
        from middleware.upload import save_file
        from fastapi.exceptions import HTTPException
        fake_content = b"<html><body>malicious</body></html>"
        f = make_upload_file("fake.jpg", fake_content, "image/jpeg")
        with pytest.raises(HTTPException) as exc_info:
            save_file(f)
        assert exc_info.value.status_code == 1001
        assert "伪造文件" in exc_info.value.detail

    def test_save_exe_rejected(self):
        """EXE 文件伪装为图片应被拒绝"""
        from middleware.upload import save_file
        from fastapi.exceptions import HTTPException
        exe_content = b"MZ\x90\x00" + b"\x00" * 1024
        f = make_upload_file("malware.jpg", exe_content, "image/jpeg")
        with pytest.raises(HTTPException) as exc_info:
            save_file(f)
        assert exc_info.value.status_code == 1001
