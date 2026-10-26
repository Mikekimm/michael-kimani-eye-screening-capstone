import io
import os
import tempfile

# Must run before any ``src`` import so the app under test never writes into the repo.
os.environ.setdefault("SCREENING_DATA_DIR", tempfile.mkdtemp(prefix="screening-test-"))

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


# ---- shared helpers for the storage / sync / API tests ---------------------------
from src.classifier import BaseClassifier  # noqa: E402
from src.quality import QualityReport  # noqa: E402
from src.result import ScreeningResult  # noqa: E402
from src.storage import ScreeningRepository  # noqa: E402


class StubClassifier(BaseClassifier):
    """Returns a fixed probability, so tests never need TensorFlow."""

    def __init__(self, probability=0.8):
        self.probability = probability

    @property
    def name(self):
        return "stub"

    def predict_proba(self, batch):
        return self.probability


def make_result(probability=0.8, threshold=0.5, model_version="test-model-1"):
    quality = QualityReport((), ("Image looks blurry; retake the photo if possible.",), 42.0, 110.0, 35.0)
    return ScreeningResult(probability, threshold, model_version, quality)


@pytest.fixture
def repo(tmp_path):
    return ScreeningRepository(tmp_path / "local.db", tmp_path / "images")


def save_one(repo, probability=0.8, patient="PT-001", side="left", image=None):
    return repo.add_screening(
        make_result(probability), image or encode(make_fundus_like(seed=3)),
        patient, side, "nurse-1", "stub")
