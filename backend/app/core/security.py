"""Password hashing (Argon2id) and JWT access/refresh tokens."""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher as _Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .errors import AuthenticationError


class PasswordHasher:
    """Argon2id with the library's recommended parameters."""

    def __init__(self) -> None:
        self._hasher = _Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    role: str
    token_type: str
    jti: str
    expires_at: datetime


class TokenService:
    """Issues and validates signed JWTs. Refresh tokens carry a ``jti`` so logout can revoke them."""

    ACCESS = "access"
    REFRESH = "refresh"

    def __init__(self, secret: str, algorithm: str, access_ttl: timedelta, refresh_ttl: timedelta):
        self._secret = secret
        self._algorithm = algorithm
        self._ttl = {self.ACCESS: access_ttl, self.REFRESH: refresh_ttl}

    def issue(self, user_id: str, role: str, token_type: str) -> tuple[str, TokenClaims]:
        now = datetime.now(timezone.utc)
        claims = TokenClaims(user_id, role, token_type, uuid.uuid4().hex, now + self._ttl[token_type])
        payload = {
            "sub": user_id, "role": role, "type": token_type, "jti": claims.jti,
            "iat": now, "exp": claims.expires_at,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm), claims

    def decode(self, token: str, expected_type: str) -> TokenClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Session expired. Please sign in again.") from None
        except jwt.PyJWTError:
            raise AuthenticationError("Invalid token.") from None
        if payload.get("type") != expected_type:
            raise AuthenticationError("Wrong token type.")
        return TokenClaims(
            user_id=payload["sub"], role=payload["role"], token_type=payload["type"],
            jti=payload["jti"], expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc),
        )
