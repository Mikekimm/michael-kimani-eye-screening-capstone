"""Stores uploaded fundus images on disk under random names (no patient data in file names)."""
import uuid
from pathlib import Path

from ..core.errors import NotFoundError

_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png"}
MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png"}


class ImageStore:
    def __init__(self, root: Path):
        self._root = Path(root)

    def save(self, data: bytes, image_format: str) -> str:
        self._root.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex + _EXTENSIONS.get(image_format, ".jpg")
        (self._root / name).write_bytes(data)
        return name

    def delete(self, name: str) -> None:
        (self._root / name).unlink(missing_ok=True)

    def path_for(self, name: str) -> Path:
        path = (self._root / name).resolve()
        # Guard against path traversal from a tampered database value.
        if path.parent != self._root.resolve() or not path.exists():
            raise NotFoundError("Image not found.")
        return path
