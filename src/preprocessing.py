"""Image loading and preprocessing, kept identical to the training pipeline."""
import io
from pathlib import Path
from typing import BinaryIO, Union

import numpy as np
from PIL import Image, UnidentifiedImageError

from .config import IMG_SIZE
from .exceptions import InvalidImageError

ImageSource = Union[bytes, bytearray, BinaryIO, str, Path]

_INTERPOLATION = {
    "nearest": Image.NEAREST,
    "bilinear": Image.BILINEAR,
    "bicubic": Image.BICUBIC,
}


class ImagePreprocessor:
    """Decodes an image source and turns it into a model-ready batch.

    The default interpolation is "nearest" because the training generators
    (Keras ``flow_from_dataframe``) resize with nearest-neighbour by default.
    Using the same resize at inference avoids train/serve skew.
    """

    def __init__(self, target_size=IMG_SIZE, interpolation: str = "nearest"):
        if interpolation not in _INTERPOLATION:
            raise ValueError(f"Unknown interpolation: {interpolation!r}")
        self._target_size = tuple(target_size)
        self._resample = _INTERPOLATION[interpolation]

    @property
    def target_size(self):
        return self._target_size

    def load(self, source: ImageSource) -> Image.Image:
        """Decode ``source`` into an RGB PIL image or raise InvalidImageError."""
        try:
            if isinstance(source, (bytes, bytearray)):
                source = io.BytesIO(source)
            image = Image.open(source)
            image.load()  # force a full decode so truncated files fail here
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidImageError("The file could not be read as an image.") from exc
        return self._to_rgb(image)

    @staticmethod
    def _to_rgb(image: Image.Image) -> Image.Image:
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (0, 0, 0))
            background.paste(rgba, mask=rgba.split()[-1])
            return background
        return image.convert("RGB")

    def to_batch(self, image: Image.Image) -> np.ndarray:
        """Resize and scale to [-1, 1] (MobileNetV2 preprocessing), shape (1,H,W,3)."""
        resized = image.resize(self._target_size, self._resample)
        array = np.asarray(resized, dtype=np.float32)
        array = array / 127.5 - 1.0
        return array[np.newaxis, ...]
