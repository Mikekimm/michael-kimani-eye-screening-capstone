"""Admin user management, including approving or rejecting self-registered health workers."""
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, PermissionDeniedError
from ..core.security import PasswordHasher
from ..models import User
from ..models.enums import AccountStatus
from ..repositories import UserRepository
from ..schemas import AdminUserCreate, UserUpdate
from .audit import AuditService
from .email import EmailSender


class UserService:
    def __init__(self, session: Session, users: UserRepository, hasher: PasswordHasher, audit: AuditService,
                 email: EmailSender | None = None, app_base_url: str = ""):
        self._session = session
        self._users = users
        self._hasher = hasher
        self._audit = audit
        self._email = email
        self._app_base_url = app_base_url.rstrip("/")

    def list(self) -> Sequence[User]:
        return self._users.list()

    def create(self, admin: User, request: AdminUserCreate) -> User:
        if self._users.by_email(request.email):
            raise ConflictError("An account with this email already exists.")
        user = self._users.add(User(email=request.email.lower(), full_name=request.full_name,
                                    password_hash=self._hasher.hash(request.password), role=request.role,
                                    status=AccountStatus.APPROVED, facility=request.facility))
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
        if changes.facility is not None and changes.facility != user.facility:
            self._audit.record(admin.id, "user.facility_set", "user", user.id)
            user.facility = changes.facility
        if changes.role is not None and changes.role != user.role:
            self._audit.record(admin.id, f"user.role_changed:{user.role.value}->{changes.role.value}", "user", user.id)
            user.role = changes.role
        if changes.is_active is not None and changes.is_active != user.is_active:
            self._audit.record(admin.id, "user.activated" if changes.is_active else "user.deactivated", "user", user.id)
            user.is_active = changes.is_active
        if changes.status is not None and changes.status != user.status:
            # Approving grants the role the admin chose, or the one requested at sign-up; rejecting keeps the
            # record for audit. The requested role never grants anything by itself.
            if (changes.status == AccountStatus.APPROVED and changes.role is None
                    and user.requested_role and user.requested_role != user.role):
                self._audit.record(admin.id, f"user.role_changed:{user.role.value}->{user.requested_role.value}",
                                   "user", user.id)
                user.role = user.requested_role
            self._audit.record(admin.id, f"user.{changes.status.value}", "user", user.id)
            user.status = changes.status
            user.status_reason = changes.status_reason if changes.status == AccountStatus.REJECTED else None
            self._session.commit()
            self._notify_decision(user)
        self._session.commit()
        return user

    def _notify_decision(self, user: User) -> None:
        """Emails the person the outcome of their registration, so nobody waits without knowing."""
        if self._email is None or user.status == AccountStatus.PENDING:
            return
        if user.status == AccountStatus.APPROVED:
            subject = "Your Retinal Screening account is approved"
            body = (f"Hello {user.full_name},\n\nYour clinic administrator has approved your account. "
                    f"You can now sign in at {self._app_base_url}/login with the email and password you chose.")
        else:
            subject = "Your Retinal Screening registration was not approved"
            body = (f"Hello {user.full_name},\n\nYour clinic administrator could not confirm your registration "
                    f"(who you are or where you work).\nReason: {user.status_reason}\n\n"
                    "Contact your clinic administrator if you think this is a mistake.")
        self._email.send(to=user.email, subject=subject, body=body)
