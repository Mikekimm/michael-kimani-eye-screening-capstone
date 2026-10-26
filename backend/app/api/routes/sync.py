from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from ...schemas import SyncPullResponse, SyncPushRequest, SyncPushResponse
from ...services.sync import SyncService
from ..deps import HealthWorker, get_sync_service

router = APIRouter(prefix="/sync", tags=["sync"])
Sync = Annotated[SyncService, Depends(get_sync_service)]


@router.post("/push", response_model=SyncPushResponse)
def push(body: SyncPushRequest, user: HealthWorker, sync: Sync,
         x_sync_attempt: Annotated[int, Header(ge=1, le=1000)] = 1):
    return SyncPushResponse(results=sync.push(user, body, attempt=x_sync_attempt))


@router.get("/pull", response_model=SyncPullResponse)
def pull(user: HealthWorker, sync: Sync, since: Annotated[datetime | None, Query()] = None):
    return sync.pull(user, since)
