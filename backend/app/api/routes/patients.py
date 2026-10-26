from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from ...schemas import PatientCreate, PatientOut, ScreeningOut
from ...services.patients import PatientService
from ...services.presenters import patient_out, screening_out
from ...services.screenings import ScreeningService
from ..deps import ClinicalUser, HealthWorker, get_patient_service, get_screening_service

router = APIRouter(prefix="/patients", tags=["patients"])
Patients = Annotated[PatientService, Depends(get_patient_service)]


@router.get("", response_model=list[PatientOut])
def search_patients(user: HealthWorker, patients: Patients, q: Annotated[str | None, Query(max_length=40)] = None):
    return [patient_out(p) for p in patients.search(user, q)]


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def register_patient(body: PatientCreate, user: HealthWorker, patients: Patients, response: Response):
    patient, duplicate = patients.register(user, body)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return patient_out(patient)


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: str, user: ClinicalUser, patients: Patients):
    return patient_out(patients.get(user, patient_id))


@router.get("/{patient_id}/screenings", response_model=list[ScreeningOut])
def patient_screenings(patient_id: str, user: HealthWorker, patients: Patients,
                       screenings: Annotated[ScreeningService, Depends(get_screening_service)]):
    patients.get(user, patient_id)  # access check
    return [screening_out(s) for s in screenings.list_mine(user, patient_id=patient_id)]
