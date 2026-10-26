"""Lightweight image-quality checks that run before the model is called.

Blocking issues stop the screening (the result would be meaningless).
Warnings are shown to the user but do not stop the screening, because these
heuristics can be wrong and must never silently reject a valid image.
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
        min_vignette_gap: float = 15.0,
    ):
        self._min_side = min_side
        self._min_contrast = min_contrast
        self._min_sharpness = min_sharpness
        self._brightness_bounds = brightness_bounds
        self._min_vignette_gap = min_vignette_gap

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
        else:
            low, high = self._brightness_bounds
            if brightness < low:
                warnings.append("Image is very dark; results may be unreliable.")
            elif brightness > high:
                warnings.append("Image is very bright; results may be unreliable.")
            if sharpness < self._min_sharpness:
                warnings.append("Image looks blurry; retake the photo if possible.")
            if self._vignette_gap(gray) < self._min_vignette_gap:
                warnings.append(
                    "Image does not look like a retinal fundus photograph "
                    "(no dark border around a bright central field)."
                )

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

    @staticmethod
    def _vignette_gap(gray: np.ndarray) -> float:
        """Centre brightness minus corner brightness (fundus photos are circular)."""
        h, w = gray.shape
        ph, pw = max(1, int(h * 0.12)), max(1, int(w * 0.12))
        corners = np.concatenate(
            [
                gray[:ph, :pw].ravel(),
                gray[:ph, -pw:].ravel(),
                gray[-ph:, :pw].ravel(),
                gray[-ph:, -pw:].ravel(),
            ]
        )
        centre = gray[h // 2 - ph : h // 2 + ph, w // 2 - pw : w // 2 + pw]
        return float(centre.mean() - corners.mean())
