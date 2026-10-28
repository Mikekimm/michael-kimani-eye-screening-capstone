import pytest
from PIL import Image, ImageDraw, ImageFilter

from app.ml.quality import NOT_FUNDUS_MESSAGE, FundusCheck, ImageQualityChecker
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


def test_random_noise_is_not_a_fundus_photo():
    import numpy as np
    noise = np.random.default_rng(1).integers(0, 255, (300, 300, 3), dtype=np.uint8)
    report = ImageQualityChecker().assess(Image.fromarray(noise))
    assert not report.is_usable
    assert report.blocking_issues == (NOT_FUNDUS_MESSAGE,)


def _screenshot_like() -> Image.Image:
    """White page with grey text bars and a coloured button, like an app screenshot."""
    page = Image.new("RGB", (390, 844), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    for y in range(80, 800, 40):
        draw.rectangle((20, y, 360, y + 12), fill=(90, 90, 90))
    draw.rectangle((20, 700, 360, 750), fill=(16, 100, 90))
    return page


def _photo_without_border() -> Image.Image:
    """A colourful scene that fills the frame (no dark circular border), like a face or a flower."""
    import numpy as np
    yy, xx = np.mgrid[0:300, 0:300]
    pixels = np.stack([150 + 60 * np.sin(xx / 30), 120 + 50 * np.cos(yy / 25), 100 + 0 * xx], axis=-1)
    return Image.fromarray(pixels.clip(0, 255).astype("uint8"), "RGB")


def _grey_field_on_black() -> Image.Image:
    """Dark border and bright centre but grey, not reddish: e.g. a lamp photographed at night."""
    image = make_fundus_like()
    grey = image.convert("L")
    return Image.merge("RGB", (grey, grey, grey))


@pytest.mark.parametrize("make", [_screenshot_like, _photo_without_border, _grey_field_on_black])
def test_non_eye_images_are_blocked_before_any_model_runs(make):
    report = ImageQualityChecker().assess(make())
    assert not report.is_usable and NOT_FUNDUS_MESSAGE in report.blocking_issues


@pytest.mark.parametrize("brightness", [0.25, 0.6, 1.0])
def test_fundus_like_images_pass_the_fundus_check(brightness):
    image = make_fundus_like(brightness=brightness)
    assert FundusCheck().looks_like_fundus(image)
    assert ImageQualityChecker().assess(image).is_usable


def test_fundus_check_reports_the_values_it_decided_on(fundus_image):
    measured = FundusCheck().measure(fundus_image)
    assert measured["corner_brightness"] < 1 and measured["red_green_ratio"] > 2
    assert 0.5 < measured["field_fraction"] < 0.75


def test_sharpness_decreases_with_blur(fundus_image):
    checker = ImageQualityChecker()
    sharp = checker.assess(fundus_image).sharpness
    soft = checker.assess(fundus_image.filter(ImageFilter.GaussianBlur(4))).sharpness
    assert soft < sharp
