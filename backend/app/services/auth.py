"""Authentication use cases: sign-up, login, refresh-token rotation, logout."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..core.errors import AuthenticationError, ConflictError
from ..core.security import PasswordHasher, TokenService
from ..core.throttle import LoginThrottle
from ..models import RefreshToken, User
from ..models.enums import Role
from ..repositories import RefreshTokenRepository, UserRepository
from ..schemas import RegisterRequest, TokenPair
from .audit import AuditService


class AuthService:
    def __init__(self, session: Session, users: UserRepository, refresh_tokens: RefreshTokenRepository,
                 hasher: PasswordHasher, tokens: TokenService, audit: AuditService, access_ttl_seconds: int,
                 throttle: LoginThrottle):
        self._session = session
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._hasher = hasher
        self._tokens = tokens
        self._audit = audit
        self._access_ttl_seconds = access_ttl_seconds
        self._throttle = throttle

    def register(self, request: RegisterRequest) -> User:
        """Public sign-up always creates a health worker; roles are only granted by an admin."""
        if self._users.by_email(request.email):
            raise ConflictError("An account with this email already exists.")
        user = self._users.add(User(email=request.email.lower(), full_name=request.full_name,
                                    password_hash=self._hasher.hash(request.password),
                                    role=Role.HEALTH_WORKER))
        self._audit.record(user.id, "user.registered", "user", user.id)
        self._session.commit()
        return user

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
        if user is None or not user.is_active:
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
        if user is None or not user.is_active:
            raise AuthenticationError("Account not found or deactivated.")
        return user

    def _issue_pair(self, user: User) -> TokenPair:
        access, _ = self._tokens.issue(user.id, user.role.value, TokenService.ACCESS)
        refresh, claims = self._tokens.issue(user.id, user.role.value, TokenService.REFRESH)
        self._refresh_tokens.add(RefreshToken(jti=claims.jti, user_id=user.id, expires_at=claims.expires_at))
        return TokenPair(access_token=access, refresh_token=refresh, expires_in=self._access_ttl_seconds)
