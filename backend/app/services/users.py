"""Admin user management."""
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, PermissionDeniedError
from ..core.security import PasswordHasher
from ..models import User
from ..repositories import UserRepository
from ..schemas import AdminUserCreate, UserUpdate
from .audit import AuditService


class UserService:
    def __init__(self, session: Session, users: UserRepository, hasher: PasswordHasher, audit: AuditService):
        self._session = session
        self._users = users
        self._hasher = hasher
        self._audit = audit

    def list(self) -> Sequence[User]:
        return self._users.list()

    def create(self, admin: User, request: AdminUserCreate) -> User:
        if self._users.by_email(request.email):
            raise ConflictError("An account with this email already exists.")
        user = self._users.add(User(email=request.email.lower(), full_name=request.full_name,
                                    password_hash=self._hasher.hash(request.password), role=request.role))
        self._audit.record(admin.id, "user.created", "user", user.id)
        self._session.commit()
        return user

    def update(self, admin: User, user_id: str, changes: UserUpdate) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if user.id == admin.id:
            # Prevents an admin locking everyone out by demoting or deactivating themselves.
            raise PermissionDeniedError("You cannot change your own role or status.")
        if changes.role is not None and changes.role != user.role:
            self._audit.record(admin.id, f"user.role_changed:{user.role.value}->{changes.role.value}", "user", user.id)
            user.role = changes.role
        if changes.is_active is not None and changes.is_active != user.is_active:
            self._audit.record(admin.id, "user.activated" if changes.is_active else "user.deactivated", "user", user.id)
            user.is_active = changes.is_active
        self._session.commit()
        return user
