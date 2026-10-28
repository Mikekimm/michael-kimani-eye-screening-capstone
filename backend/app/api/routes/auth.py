from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from ...schemas import (
    ForgotPasswordRequest, LoginRequest, RefreshRequest, RegisterRequest, ResetPasswordRequest, TokenPair, UserOut,
)
from ...services.auth import AuthService
from ..deps import CurrentUser, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
Auth = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, auth: Auth, request: Request):
    """Public sign-up. Creates a health worker account that waits for an admin's approval.
    Limited per client address (HTTP 429 when exceeded)."""
    return auth.register(body, client=request.client.host if request.client else None)


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


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: ForgotPasswordRequest, auth: Auth):
    """Emails a one-time reset link. The answer is the same whether or not the email is registered."""
    auth.request_password_reset(body.email)
    return {"message": "If an account exists for this email, a reset link has been sent."}


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetPasswordRequest, auth: Auth):
    """Sets a new password from a valid link and signs the account out on every device."""
    auth.reset_password(body.token, body.password)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
