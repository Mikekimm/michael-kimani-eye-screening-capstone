"""ScreeningWorkflow saves a record only when screening succeeded."""
import pytest
from PIL import Image

from src.exceptions import ImageQualityError, InvalidImageError, RecordValidationError
from src.service import ScreeningService
from src.workflow import ScreeningWorkflow
from tests.conftest import StubClassifier, encode, make_fundus_like


def build(repo, probability=0.8):
    return ScreeningWorkflow(ScreeningService(StubClassifier(probability), model_version="wf-1"), repo)


def test_successful_run_saves_a_pending_record(repo):
    record, result = build(repo).run(encode(make_fundus_like()), "PT-100", "left", "nurse-1")
    assert result.dr_detected and record.needs_review
    assert (record.laterality.value, record.model_version) == ("left", "wf-1")
    assert record.classifier_name == "stub" and record.created_by == "nurse-1"
    assert repo.stats()["screenings"] == 1


def test_borderline_result_is_saved_as_needing_review(repo):
    record, result = build(repo, probability=0.45).run(
        encode(make_fundus_like()), "PT-101", "right", "nurse-1")
    assert not result.dr_detected and record.needs_review


def test_corrupt_image_saves_nothing(repo):
    with pytest.raises(InvalidImageError):
        build(repo).run(b"garbage", "PT-102", "left", "nurse-1")
    assert repo.stats()["screenings"] == 0


def test_unusable_quality_saves_nothing(repo):
    blank = encode(Image.new("RGB", (300, 300), (90, 90, 90)))
    with pytest.raises(ImageQualityError):
        build(repo).run(blank, "PT-103", "left", "nurse-1")
    assert repo.stats()["screenings"] == 0


def test_invalid_patient_reference_saves_nothing(repo):
    with pytest.raises(RecordValidationError):
        build(repo).run(encode(make_fundus_like()), "Jane Doe", "left", "nurse-1")
    assert repo.stats()["screenings"] == 0
