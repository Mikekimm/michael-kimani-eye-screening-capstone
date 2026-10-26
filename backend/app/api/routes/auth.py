from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from ...schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserOut
from ...services.auth import AuthService
from ..deps import CurrentUser, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
Auth = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, auth: Auth):
    """Public sign-up. Always creates a health worker account."""
    return auth.register(body)


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, auth: Auth, request: Request):
    """Repeated failures for one email from one address are throttled (HTTP 429)."""
    return auth.login(body.email, body.password, client=request.client.host if request.client else None)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, auth: Auth):
    return auth.refresh(body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, auth: Auth):
    auth.logout(body.refresh_token)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
