from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.utils.file_utils import get_extension, is_allowed_extension


REQUIRED_STORAGE_FOLDERS = ("uploads", "processed", "outputs", "chroma")


def ensure_storage_directories() -> None:
    base_path = Path(settings.storage_dir)
    for folder in REQUIRED_STORAGE_FOLDERS:
        (base_path / folder).mkdir(parents=True, exist_ok=True)


class StoredUpload:
    def __init__(
        self,
        *,
        original_filename: str,
        stored_filename: str,
        file_type: str,
        content_type: str | None,
        size_bytes: int,
        path: Path,
    ) -> None:
        self.original_filename = original_filename
        self.stored_filename = stored_filename
        self.file_type = file_type
        self.content_type = content_type
        self.size_bytes = size_bytes
        self.path = path


async def save_upload_file(upload_file: UploadFile) -> StoredUpload:
    if upload_file.filename is None or not upload_file.filename.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No file was provided.",
        )

    original_filename = upload_file.filename
    if not is_allowed_extension(original_filename, settings.allowed_upload_extensions):
        allowed = ", ".join(sorted(settings.allowed_upload_extensions))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unsupported file type. Allowed extensions: {allowed}.",
        )

    file_type = get_extension(original_filename)
    stored_filename = f"{uuid4().hex}.{file_type}"
    upload_dir = Path(settings.storage_dir) / "uploads"
    destination = upload_dir / stored_filename

    size_bytes = 0
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            while chunk := await upload_file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > settings.max_upload_size_bytes:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=(
                            "Uploaded file is too large. "
                            f"Maximum size is {settings.max_upload_size_mb} MB."
                        ),
                    )
                output.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise RuntimeError("Failed to store uploaded file.") from exc
    finally:
        await upload_file.close()

    if size_bytes == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty.",
        )

    return StoredUpload(
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_type=file_type,
        content_type=upload_file.content_type,
        size_bytes=size_bytes,
        path=destination,
    )
