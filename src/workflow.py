"""Use case: screen one image and save the outcome locally in a single step."""
from typing import Tuple

from .domain import ScreeningRecord
from .result import ScreeningResult
from .service import ScreeningService
from .storage import ScreeningRepository


class ScreeningWorkflow:
    """Combines the inference service and the local store.

    If screening fails (bad image, unusable quality, model error) nothing is saved,
    so the local database only ever holds records that have a valid result.
    """

    def __init__(self, service: ScreeningService, repository: ScreeningRepository):
        self._service = service
        self._repository = repository

    def run(self, image_bytes: bytes, patient_ref: str, laterality: str,
            operator: str) -> Tuple[ScreeningRecord, ScreeningResult]:
        result = self._service.screen(image_bytes)
        record = self._repository.add_screening(
            result=result,
            image_bytes=image_bytes,
            patient_ref=patient_ref,
            laterality=laterality,
            created_by=operator,
            classifier_name=self._service.classifier_name,
        )
        return record, result
