from pathlib import Path


def get_file_size(path: Path) -> int:
    return path.stat().st_size


def safe_filename(filename: str) -> str:
    allowed = []
    for char in filename.strip():
        if char.isalnum() or char in {".", "-", "_"}:
            allowed.append(char)
        else:
            allowed.append("_")
    cleaned = "".join(allowed).strip("._")
    return cleaned or "uploaded_file"


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def is_allowed_extension(filename: str, allowed_extensions: set[str]) -> bool:
    extension = get_extension(filename)
    return bool(extension and extension in allowed_extensions)
