from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from ...models.enums import Eye
from ...schemas import ScreeningCreated, ScreeningOut
from ...services.image_store import MEDIA_TYPES
from ...services.presenters import screening_out
from ...services.screenings import ScreeningService
from ..deps import ClinicalUser, HealthWorker, get_screening_service

router = APIRouter(prefix="/screenings", tags=["screenings"])
Screenings = Annotated[ScreeningService, Depends(get_screening_service)]


@router.post("", response_model=ScreeningCreated, status_code=status.HTTP_201_CREATED)
async def create_screening(
    user: HealthWorker,
    screenings: Screenings,
    response: Response,
    image: Annotated[UploadFile, File(description="Fundus photo, JPEG or PNG")],
    patient_id: Annotated[str, Form()],
    eye: Annotated[Eye, Form()],
    client_uuid: Annotated[str, Form(min_length=8, max_length=36)],
    captured_at: Annotated[datetime, Form()],
    x_sync_attempt: Annotated[int, Header(ge=1, le=1000)] = 1,
):
    """Runs every available condition model. Re-sending the same client_uuid returns the
    original record with 200 instead of creating a duplicate."""
    data = await image.read()
    screening, duplicate = screenings.create(
        user, patient_id=patient_id, eye=eye, client_uuid=client_uuid, captured_at=captured_at,
        content_type=image.content_type, data=data, sync_attempt=x_sync_attempt)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return screening_out(screening, ScreeningCreated, duplicate=duplicate)


@router.get("", response_model=list[ScreeningOut])
def list_screenings(user: HealthWorker, screenings: Screenings,
                    limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return [screening_out(s) for s in screenings.list_mine(user, limit=limit)]


@router.get("/{screening_id}", response_model=ScreeningOut)
def get_screening(screening_id: str, user: ClinicalUser, screenings: Screenings):
    return screening_out(screenings.get(user, screening_id))


@router.post("/{screening_id}/refer", response_model=ScreeningOut)
def refer_screening(screening_id: str, user: HealthWorker, screenings: Screenings):
    """Send a non-referred screening to the specialist queue (reason: manual)."""
    return screening_out(screenings.refer(user, screening_id))


@router.get("/{screening_id}/image", response_class=FileResponse)
def get_image(screening_id: str, user: ClinicalUser, screenings: Screenings):
    path = screenings.image_path(user, screening_id)
    return FileResponse(path, media_type=MEDIA_TYPES.get(path.suffix, "application/octet-stream"),
                        headers={"Cache-Control": "private, no-store"})
