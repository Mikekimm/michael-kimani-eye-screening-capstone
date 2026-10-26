from PIL import Image, ImageFilter

from app.ml.quality import ImageQualityChecker
from tests.conftest import make_fundus_like


def test_good_fundus_like_image_has_no_issues(fundus_image):
    report = ImageQualityChecker().assess(fundus_image)
    assert report.is_usable
    assert report.warnings == ()


def test_blank_image_is_blocked():
    report = ImageQualityChecker().assess(Image.new("RGB", (300, 300), (128, 128, 128)))
    assert not report.is_usable
    assert any("blank" in issue.lower() for issue in report.blocking_issues)


def test_tiny_image_is_blocked():
    report = ImageQualityChecker().assess(make_fundus_like(size=300).resize((32, 32)))
    assert not report.is_usable
    assert any("too small" in issue.lower() for issue in report.blocking_issues)


def test_blurry_image_gets_warning_but_is_usable(fundus_image):
    blurred = fundus_image.filter(ImageFilter.GaussianBlur(8))
    report = ImageQualityChecker().assess(blurred)
    assert report.is_usable
    assert any("blurry" in warning.lower() for warning in report.warnings)


def test_dark_image_gets_warning():
    report = ImageQualityChecker().assess(make_fundus_like(brightness=0.25))
    assert report.is_usable
    assert any("dark" in warning.lower() for warning in report.warnings)


def test_non_fundus_noise_gets_warning_not_block():
    import numpy as np
    noise = np.random.default_rng(1).integers(0, 255, (300, 300, 3), dtype=np.uint8)
    report = ImageQualityChecker().assess(Image.fromarray(noise))
    assert report.is_usable
    assert any("fundus" in warning.lower() for warning in report.warnings)


def test_sharpness_decreases_with_blur(fundus_image):
    checker = ImageQualityChecker()
    sharp = checker.assess(fundus_image).sharpness
    soft = checker.assess(fundus_image.filter(ImageFilter.GaussianBlur(4))).sharpness
    assert soft < sharp
