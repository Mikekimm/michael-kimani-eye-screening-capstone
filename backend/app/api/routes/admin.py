from typing import Annotated

from fastapi import APIRouter, Depends, status

from ...schemas import AdminUserCreate, AnalyticsOut, UserOut, UserUpdate
from ...services.analytics import AnalyticsService
from ...services.users import UserService
from ..deps import Admin, get_analytics_service, get_user_service

router = APIRouter(prefix="/admin", tags=["admin"])
Users = Annotated[UserService, Depends(get_user_service)]


@router.get("/users", response_model=list[UserOut])
def list_users(_admin: Admin, users: Users):
    return users.list()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: AdminUserCreate, admin: Admin, users: Users):
    return users.create(admin, body)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, admin: Admin, users: Users):
    return users.update(admin, user_id, body)


@router.get("/analytics", response_model=AnalyticsOut)
def analytics(admin: Admin, service: Annotated[AnalyticsService, Depends(get_analytics_service)]):
    return service.summary(admin)
