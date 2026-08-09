from pathlib import Path
from uuid import uuid4

from app.core.config import PROJECT_ROOT

STORAGE_ROOT = (PROJECT_ROOT / "storage" / "documents").resolve()
ALLOWED_FILE_EXTENSIONS = {".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".pdf", ".docx"}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def validate_filename(filename: str | None) -> str:
    if not filename:
        raise ValueError("上传文件必须包含文件名")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_FILE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_FILE_EXTENSIONS))
        raise ValueError(f"暂只支持以下文件类型：{allowed}")
    return suffix


def save_upload(filename: str | None, content: bytes) -> tuple[str, str]:
    suffix = validate_filename(filename)
    if not content:
        raise ValueError("上传文件不能为空")
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError("上传文件不能超过 10 MB")

    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    relative_path = Path("storage") / "documents" / f"{uuid4().hex}{suffix}"
    absolute_path = resolve_storage_path(str(relative_path))
    absolute_path.write_bytes(content)
    return str(relative_path).replace("\\", "/"), suffix


def resolve_storage_path(relative_path: str) -> Path:
    absolute_path = (PROJECT_ROOT / relative_path).resolve()
    if not absolute_path.is_relative_to(STORAGE_ROOT):
        raise ValueError("非法文件存储路径")
    return absolute_path


def delete_stored_file(relative_path: str | None) -> None:
    if not relative_path:
        return
    try:
        absolute_path = resolve_storage_path(relative_path)
    except ValueError:
        return
    if absolute_path.is_file():
        absolute_path.unlink()
