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

    Each model must be fed the resize it was trained with (its model card says which): the ODIR
    models used nearest-neighbour (Keras ``flow_from_dataframe`` default), DR v2 used TensorFlow's
    anti-aliased bilinear resize. Feeding DR v2 nearest-neighbour input flipped 6 of 24 parity
    decisions, so the choice is not cosmetic.
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
        if self._resample == Image.NEAREST:
            array = np.asarray(image.resize(self._target_size, self._resample), dtype=np.float32)
        else:
            array = self._resize_float(np.asarray(image, dtype=np.float32))
        array = array / 127.5 - 1.0
        return array[np.newaxis, ...]

    def _resize_float(self, array: np.ndarray) -> np.ndarray:
        """Resizes each channel in float32, like tf.image.resize, instead of rounding back to 8 bits.

        Pillow's bilinear/bicubic filters widen with the scale factor when shrinking, which is the
        same anti-aliasing as tf.image.resize(antialias=True).
        """
        channels = [np.asarray(Image.fromarray(array[..., c]).resize(self._target_size, self._resample))
                    for c in range(array.shape[-1])]
        return np.stack(channels, axis=-1)
