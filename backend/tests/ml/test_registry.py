"""ModelRegistry: discovery, checksum verification, and adding a condition with zero code change."""
import json
import shutil

import numpy as np
import pytest

from app.core.config import REPO_ROOT
from app.ml.preprocessing import ImagePreprocessor
from app.ml.registry import ModelRegistry, sha256_of

from ..conftest import make_fundus_like

CONDITIONS = ("dr", "glaucoma", "cataract")
DR_FOLDER = REPO_ROOT / "models" / "dr"


@pytest.fixture
def models_dir(tmp_path):
    shutil.copytree(DR_FOLDER, tmp_path / "dr", ignore=shutil.ignore_patterns("*.h5"))
    return tmp_path


def test_real_models_folder_registers_dr_only():
    registry = ModelRegistry(CONDITIONS).discover(REPO_ROOT / "models")
    assert registry.get("dr") is not None
    assert registry.status("dr").available
    for condition in ("glaucoma", "cataract"):
        assert registry.get(condition) is None
        assert "not available yet" in registry.status(condition).reason.lower()


def test_model_card_checksum_matches_the_shipped_file():
    card = json.loads((DR_FOLDER / "model_card.json").read_text(encoding="utf-8"))
    assert sha256_of(DR_FOLDER / card["file"]) == card["sha256"]


def test_checksum_mismatch_is_rejected(models_dir):
    with open(models_dir / "dr" / "model.tflite", "ab") as handle:
        handle.write(b"tampered")
    registry = ModelRegistry(CONDITIONS).discover(models_dir)
    assert registry.get("dr") is None
    assert "checksum" in registry.status("dr").reason.lower()


def test_invalid_card_is_rejected(models_dir):
    (models_dir / "dr" / "model_card.json").write_text("{not json", encoding="utf-8")
    registry = ModelRegistry(CONDITIONS).discover(models_dir)
    assert registry.get("dr") is None
    assert "invalid" in registry.status("dr").reason.lower()


def test_card_for_wrong_condition_is_rejected(models_dir):
    shutil.copytree(models_dir / "dr", models_dir / "cataract")
    registry = ModelRegistry(CONDITIONS).discover(models_dir)
    assert registry.get("cataract") is None
    assert "folder is 'cataract'" in registry.status("cataract").reason


def test_missing_model_file_is_rejected(models_dir):
    (models_dir / "dr" / "model.tflite").unlink()
    registry = ModelRegistry(CONDITIONS).discover(models_dir)
    assert not registry.status("dr").available


def test_dropping_a_valid_model_folder_registers_it_without_code_changes(models_dir):
    """Simulates adding a trained glaucoma model: copy files + write its card, nothing else."""
    target = models_dir / "glaucoma"
    target.mkdir()
    shutil.copy(models_dir / "dr" / "model.tflite", target / "model.tflite")
    card = json.loads((models_dir / "dr" / "model_card.json").read_text(encoding="utf-8"))
    card.update(condition="glaucoma", display_name="Glaucoma", version="glaucoma-plumbing-check")
    (target / "model_card.json").write_text(json.dumps(card), encoding="utf-8")

    registry = ModelRegistry(CONDITIONS).discover(models_dir)
    assert registry.status("glaucoma").available
    assert registry.get("glaucoma").version == "glaucoma-plumbing-check"


def test_real_model_output_is_a_probability_and_deterministic():
    model = ModelRegistry(CONDITIONS).discover(REPO_ROOT / "models").get("dr")
    batch = ImagePreprocessor().to_batch(make_fundus_like(seed=3))
    scores = [model.predict_proba(batch) for _ in range(3)]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert np.ptp(scores) == 0.0
