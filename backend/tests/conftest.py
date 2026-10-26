import io
import numpy as np
import pytest
from PIL import Image


def make_fundus_like(size: int = 300, seed: int = 0, brightness: float = 1.0) -> Image.Image:
    """Synthetic fundus-style test image: textured orange disc on a black background.

    This is a unit-test fixture only; it is never presented as a real retinal photo.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size]
    disc = np.hypot(xx - size / 2, yy - size / 2) < size * 0.45
    texture = rng.normal(0, 12, (size, size, 1))
    pixels = np.zeros((size, size, 3), dtype=np.float32)
    pixels[disc] = (np.array([200, 90, 30], dtype=np.float32) + texture[disc]).clip(0, 255)
    return Image.fromarray((pixels * brightness).astype(np.uint8), "RGB")


def encode(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def fundus_image():
    return make_fundus_like()


@pytest.fixture
def fundus_png(fundus_image):
    return encode(fundus_image, "PNG")
