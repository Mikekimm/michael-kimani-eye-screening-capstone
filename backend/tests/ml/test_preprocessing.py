import numpy as np
import pytest
from PIL import Image

from app.ml.exceptions import InvalidImageError
from app.ml.preprocessing import ImagePreprocessor
from tests.conftest import encode


def test_batch_shape_dtype_and_range(fundus_image):
    batch = ImagePreprocessor().to_batch(fundus_image)
    assert batch.shape == (1, 224, 224, 3)
    assert batch.dtype == np.float32
    assert batch.min() >= -1.0 and batch.max() <= 1.0


def test_scaling_matches_mobilenet_v2_convention():
    white = Image.new("RGB", (10, 10), (255, 255, 255))
    black = Image.new("RGB", (10, 10), (0, 0, 0))
    preprocessor = ImagePreprocessor(target_size=(4, 4))
    assert np.allclose(preprocessor.to_batch(white), 1.0)
    assert np.allclose(preprocessor.to_batch(black), -1.0)


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_loads_common_formats(fundus_image, fmt):
    assert ImagePreprocessor().load(encode(fundus_image, fmt)).mode == "RGB"


def test_grayscale_and_rgba_are_converted_to_rgb(fundus_image):
    assert ImagePreprocessor().load(encode(fundus_image.convert("L"))).mode == "RGB"
    assert ImagePreprocessor().load(encode(fundus_image.convert("RGBA"))).mode == "RGB"


@pytest.mark.parametrize("bad", [b"", b"not an image at all", b"\x89PNG\r\n\x1a\ntruncated"])
def test_undecodable_data_raises_invalid_image_error(bad):
    with pytest.raises(InvalidImageError):
        ImagePreprocessor().load(bad)


def test_truncated_real_image_raises(fundus_png):
    with pytest.raises(InvalidImageError):
        ImagePreprocessor().load(fundus_png[: len(fundus_png) // 3])


def test_unknown_interpolation_rejected():
    with pytest.raises(ValueError):
        ImagePreprocessor(interpolation="magic")


def test_float_bilinear_resize_does_not_round_to_8_bits(fundus_image):
    batch = ImagePreprocessor(interpolation="bilinear").to_batch(fundus_image)
    pixels = (batch + 1.0) * 127.5
    assert batch.shape == (1, 224, 224, 3) and batch.dtype == np.float32
    assert not np.allclose(pixels, np.round(pixels))  # kept in float, like tf.image.resize


def test_nearest_resize_only_copies_existing_pixel_values(fundus_image):
    pixels = (ImagePreprocessor(interpolation="nearest").to_batch(fundus_image) + 1.0) * 127.5
    assert np.allclose(pixels, np.round(pixels), atol=1e-4)
