"""Lightweight image-quality checks that run before any model is called.

Blocking issues stop the screening: no model runs and nothing is saved. That includes an image that
does not look like a retinal fundus photograph, because the classifiers cannot tell a screenshot or a
face from an eye and would still return a score. Darkness, brightness and blur are warnings only.

The fundus check is a heuristic tuned on 25 real fundus photos and 77 non-eye images
(results: docs/testing/testing_report.md and README section 9); it can still be fooled, which is stated as a known limitation.
"""
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image

_ANALYSIS_SIZE = (256, 256)


@dataclass(frozen=True)
class QualityReport:
    blocking_issues: Tuple[str, ...]
    warnings: Tuple[str, ...]
    sharpness: float
    brightness: float
    contrast: float

    @property
    def is_usable(self) -> bool:
        return not self.blocking_issues


class ImageQualityChecker:
    """Computes simple, explainable quality metrics for a fundus photograph."""

    def __init__(
        self,
        min_side: int = 64,
        min_contrast: float = 8.0,
        min_sharpness: float = 20.0,
        brightness_bounds: Tuple[float, float] = (20.0, 235.0),
        fundus: "FundusCheck | None" = None,
    ):
        self._min_side = min_side
        self._min_contrast = min_contrast
        self._min_sharpness = min_sharpness
        self._brightness_bounds = brightness_bounds
        self._fundus = fundus or FundusCheck()

    def assess(self, image: Image.Image) -> QualityReport:
        blocking, warnings = [], []

        if min(image.size) < self._min_side:
            blocking.append(
                f"Image is too small ({image.size[0]}x{image.size[1]} px); "
                f"at least {self._min_side} px per side is required."
            )

        gray = np.asarray(
            image.convert("L").resize(_ANALYSIS_SIZE, Image.BILINEAR), dtype=np.float32
        )
        brightness = float(gray.mean())
        contrast = float(gray.std())
        sharpness = self._laplacian_variance(gray)

        if contrast < self._min_contrast:
            blocking.append("Image appears blank or uniform.")
        elif not self._fundus.looks_like_fundus(image):
            blocking.append(NOT_FUNDUS_MESSAGE)
        else:
            low, high = self._brightness_bounds
            if brightness < low:
                warnings.append("Image is very dark; results may be unreliable.")
            elif brightness > high:
                warnings.append("Image is very bright; results may be unreliable.")
            if sharpness < self._min_sharpness:
                warnings.append("Image looks blurry; retake the photo if possible.")

        return QualityReport(
            blocking_issues=tuple(blocking),
            warnings=tuple(warnings),
            sharpness=sharpness,
            brightness=brightness,
            contrast=contrast,
        )

    @staticmethod
    def _laplacian_variance(gray: np.ndarray) -> float:
        """Variance of the 4-neighbour Laplacian: a standard sharpness measure."""
        laplacian = (
            -4.0 * gray[1:-1, 1:-1]
            + gray[:-2, 1:-1]
            + gray[2:, 1:-1]
            + gray[1:-1, :-2]
            + gray[1:-1, 2:]
        )
        return float(laplacian.var())


NOT_FUNDUS_MESSAGE = ("This does not look like a retinal fundus photograph (it needs a dark border around a "
                      "round, reddish view of the back of the eye). No result was produced.")


@dataclass(frozen=True)
class FundusCheck:
    """Does the image look like a fundus camera photo? All four rules must hold:

    * dark border: the corners are nearly black (the camera's circular field);
    * bright centre: the middle is clearly brighter than the corners;
    * fundus colour: the lit area is reddish (red channel above green), unlike grey or white pages;
    * a field, not a full frame: the lit area covers part of the image, not all of it.
    """
    max_corner_brightness: float = 35.0
    min_centre_gap: float = 15.0
    min_red_green_ratio: float = 1.05
    field_fraction: Tuple[float, float] = (0.40, 0.97)
    lit_level: float = 10.0

    def measure(self, image: Image.Image) -> dict[str, float]:
        rgb = np.asarray(image.convert("RGB").resize(_ANALYSIS_SIZE, Image.BILINEAR), dtype=np.float32)
        gray = rgb.mean(axis=2)
        h, w = gray.shape
        ph, pw = max(1, int(h * 0.12)), max(1, int(w * 0.12))
        corners = np.concatenate([gray[:ph, :pw].ravel(), gray[:ph, -pw:].ravel(),
                                  gray[-ph:, :pw].ravel(), gray[-ph:, -pw:].ravel()])
        centre = gray[h // 2 - ph:h // 2 + ph, w // 2 - pw:w // 2 + pw]
        lit = gray > self.lit_level
        red, green = rgb[..., 0][lit], rgb[..., 1][lit]
        return {
            "corner_brightness": float(corners.mean()),
            "centre_gap": float(centre.mean() - corners.mean()),
            "red_green_ratio": float(red.mean() / max(1.0, float(green.mean()))) if red.size else 0.0,
            "field_fraction": float(lit.mean()),
        }

    def looks_like_fundus(self, image: Image.Image) -> bool:
        m = self.measure(image)
        low, high = self.field_fraction
        return (m["corner_brightness"] <= self.max_corner_brightness
                and m["centre_gap"] >= self.min_centre_gap
                and m["red_green_ratio"] >= self.min_red_green_ratio
                and low <= m["field_fraction"] <= high)
