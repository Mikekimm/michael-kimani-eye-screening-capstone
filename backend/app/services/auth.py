"""Authentication use cases: sign-up with admin approval, login, refresh-token rotation, logout and
password reset by emailed one-time link."""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..core.errors import AppError, AuthenticationError, ConflictError, PermissionDeniedError
from ..core.security import PasswordHasher, TokenService
from ..core.throttle import LoginThrottle
from ..models import PasswordResetToken, RefreshToken, User
from ..models.enums import AccountStatus, Role
from ..repositories import PasswordResetRepository, RefreshTokenRepository, UserRepository
from ..schemas import RegisterRequest, TokenPair
from .audit import AuditService
from .email import EmailSender

PENDING_MESSAGE = "Your account is waiting for administrator approval."
REJECTED_MESSAGE = "Your registration was not approved. Contact your clinic administrator."
INVALID_RESET_MESSAGE = "This reset link is invalid, has expired or was already used. Request a new one."


@dataclass(frozen=True)
class PasswordResetConfig:
    sender: EmailSender
    app_base_url: str
    valid_minutes: int = 30


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, session: Session, users: UserRepository, refresh_tokens: RefreshTokenRepository,
                 hasher: PasswordHasher, tokens: TokenService, audit: AuditService, access_ttl_seconds: int,
                 throttle: LoginThrottle, resets: PasswordResetRepository | None = None,
                 reset_config: PasswordResetConfig | None = None, signup_throttle: LoginThrottle | None = None):
        self._session = session
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._hasher = hasher
        self._tokens = tokens
        self._audit = audit
        self._access_ttl_seconds = access_ttl_seconds
        self._throttle = throttle
        self._resets = resets
        self._reset_config = reset_config
        self._signup_throttle = signup_throttle

    def register(self, request: RegisterRequest, client: str | None = None) -> User:
        """Public sign-up records a request for access. The account is PENDING and cannot sign in; the
        requested role is stored but grants nothing (``role`` stays the least-privileged one) until an admin
        approves, possibly with a different role. The app cannot verify who the person is."""
        key = f"signup|{client or 'unknown'}"
        if self._signup_throttle is not None:
            self._signup_throttle.check(key)
            self._signup_throttle.record_failure(key)  # every attempt counts, successful or not
        if self._users.by_email(request.email):
            raise ConflictError("An account with this email already exists.")
        user = self._users.add(User(email=request.email.lower(), full_name=request.full_name,
                                    password_hash=self._hasher.hash(request.password),
                                    role=Role.HEALTH_WORKER, requested_role=request.requested_role,
                                    status=AccountStatus.PENDING, facility=request.facility))
        self._audit.record(user.id, "user.registered", "user", user.id)
        self._session.commit()
        self._notify_admins_of_sign_up(user)
        return user

    def _notify_admins_of_sign_up(self, user: User) -> None:
        """Admins hear about a new sign-up straight away instead of only when they next open the app."""
        if self._reset_config is None:
            return
        link = f"{self._reset_config.app_base_url.rstrip('/')}/admin/users"
        for admin in self._users.active_admins():
            self._reset_config.sender.send(
                to=admin.email, subject="New health worker account waiting for approval",
                body=(f"Hello {admin.full_name},\n\n{user.full_name} ({user.email}) registered as a health worker.\n"
                      f"Requested role: {user.requested_role.value.replace('_', ' ')}\n"
                      f"Health facility (as typed, not verified): {user.facility}\n\n"
                      "Check these against your staff list or the professional register, then approve or reject "
                      f"the account here:\n{link}\n\nPatients never need an account; reject any sign-up you cannot confirm."))

    def login(self, email: str, password: str, client: str | None = None) -> TokenPair:
        key = LoginThrottle.key(email, client)
        self._throttle.check(key)  # checked first, so a correct guess after the limit still fails
        user = self._users.by_email(email)
        # Same error for unknown email and wrong password, so accounts cannot be enumerated.
        if user is None or not self._hasher.verify(user.password_hash, password):
            self._throttle.record_failure(key)
            self._audit.record(user.id if user else None, "auth.login_failed")
            self._session.commit()
            raise AuthenticationError("Incorrect email or password.")
        self._throttle.reset(key)
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated. Contact an administrator.")
        # Only reached with the right password, so it does not reveal whether an email is registered.
        if user.status == AccountStatus.PENDING:
            raise PermissionDeniedError(PENDING_MESSAGE)
        if user.status == AccountStatus.REJECTED:
            raise PermissionDeniedError(REJECTED_MESSAGE)
        pair = self._issue_pair(user)
        self._audit.record(user.id, "auth.login", "user", user.id)
        self._session.commit()
        return pair

    def refresh(self, refresh_token: str) -> TokenPair:
        """Rotate: the presented refresh token is revoked and a new pair is issued."""
        claims = self._tokens.decode(refresh_token, TokenService.REFRESH)
        stored = self._refresh_tokens.get(claims.jti)
        if stored is None or stored.revoked_at is not None:
            raise AuthenticationError("Session is no longer valid. Please sign in again.")
        user = self._users.get(claims.user_id)
        if not self._may_sign_in(user):
            raise AuthenticationError("Session is no longer valid. Please sign in again.")
        stored.revoked_at = datetime.now(timezone.utc)
        pair = self._issue_pair(user)
        self._session.commit()
        return pair

    def logout(self, refresh_token: str) -> None:
        try:
            claims = self._tokens.decode(refresh_token, TokenService.REFRESH)
        except AuthenticationError:
            return  # logging out with an expired token is not an error
        stored = self._refresh_tokens.get(claims.jti)
        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(timezone.utc)
            self._audit.record(claims.user_id, "auth.logout", "user", claims.user_id)
            self._session.commit()

    def user_from_access_token(self, access_token: str) -> User:
        claims = self._tokens.decode(access_token, TokenService.ACCESS)
        user = self._users.get(claims.user_id)
        if not self._may_sign_in(user):
            raise AuthenticationError("Account not found or deactivated.")
        return user

    def request_password_reset(self, email: str) -> None:
        """Emails a one-time link valid for a short time. Always returns quietly, so the response never
        reveals whether an email is registered."""
        user = self._users.by_email(email)
        if not self._may_sign_in(user) or self._resets is None or self._reset_config is None:
            return
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        self._resets.add(PasswordResetToken(user_id=user.id, token_hash=_hash_token(token),
                                            expires_at=now + timedelta(minutes=self._reset_config.valid_minutes)))
        self._audit.record(user.id, "auth.password_reset_requested", "user", user.id)
        self._session.commit()
        link = f"{self._reset_config.app_base_url.rstrip('/')}/reset-password?token={token}"
        self._reset_config.sender.send(
            to=user.email, subject="Reset your Retinal Screening password",
            body=(f"Hello {user.full_name},\n\nSomeone asked to reset the password for this account. "
                  f"To choose a new password, open this link within {self._reset_config.valid_minutes} minutes:\n\n"
                  f"{link}\n\nThe link works once. If you did not ask for this, ignore this email; "
                  "your password stays the same."))

    def reset_password(self, token: str, new_password: str) -> None:
        """Sets the new password, uses up the link, and signs the account out everywhere."""
        if self._resets is None:
            raise AppError(INVALID_RESET_MESSAGE)
        stored = self._resets.by_hash(_hash_token(token))
        now = datetime.now(timezone.utc)
        if stored is None or stored.used_at is not None or stored.expires_at <= now:
            raise AppError(INVALID_RESET_MESSAGE)
        user = self._users.get(stored.user_id)
        if not self._may_sign_in(user):
            raise AppError(INVALID_RESET_MESSAGE)
        user.password_hash = self._hasher.hash(new_password)
        stored.used_at = now
        self._refresh_tokens.revoke_all_for(user.id, now)
        self._audit.record(user.id, "auth.password_reset", "user", user.id)
        self._session.commit()

    @staticmethod
    def _may_sign_in(user: User | None) -> bool:
        return user is not None and user.is_active and user.status == AccountStatus.APPROVED

    def _issue_pair(self, user: User) -> TokenPair:
        access, _ = self._tokens.issue(user.id, user.role.value, TokenService.ACCESS)
        refresh, claims = self._tokens.issue(user.id, user.role.value, TokenService.REFRESH)
        self._refresh_tokens.add(RefreshToken(jti=claims.jti, user_id=user.id, expires_at=claims.expires_at))
        return TokenPair(access_token=access, refresh_token=refresh, expires_in=self._access_ttl_seconds)
