"""access requests, referral questions, discarded screenings

* users: requested_role (what the person asked for; grants nothing until an admin approves),
  status_reason (why a registration was rejected); registration_number is dropped, because the app
  cannot verify it and it was never used for a decision.
* referrals: question, the health worker's note when they ask a specialist.
* screenings: discarded_at / discarded_by_id / discard_reason (soft delete; the row and the audit
  entry stay, the photo file is removed).
* diagnosis_results: auto_refer renamed refer_suggested, because nothing is sent to a specialist
  automatically any more; the health worker decides.

Revision ID: 7a3c5e9b1d20
Revises: 9d71ff1c3e7f
Create Date: 2026-10-28 09:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.core.database  # noqa: F401  (custom UTCDateTime column type)

revision: str = "7a3c5e9b1d20"
down_revision: Union[str, Sequence[str], None] = "9d71ff1c3e7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLE = sa.Enum("health_worker", "specialist", "admin", name="role", native_enum=False, length=32)


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("requested_role", _ROLE, nullable=True))
        batch_op.add_column(sa.Column("status_reason", sa.Text(), nullable=True))
        batch_op.drop_column("registration_number")
    with op.batch_alter_table("referrals", schema=None) as batch_op:
        batch_op.add_column(sa.Column("question", sa.Text(), nullable=True))
    with op.batch_alter_table("diagnosis_results", schema=None) as batch_op:
        batch_op.alter_column("auto_refer", new_column_name="refer_suggested")
    with op.batch_alter_table("screenings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("discarded_at", app.core.database.UTCDateTime(), nullable=True))
        batch_op.add_column(sa.Column("discarded_by_id", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("discard_reason", sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f("ix_screenings_discarded_at"), ["discarded_at"], unique=False)
        batch_op.create_foreign_key("fk_screenings_discarded_by_id", "users", ["discarded_by_id"], ["id"],
                                    ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("screenings", schema=None) as batch_op:
        batch_op.drop_constraint("fk_screenings_discarded_by_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_screenings_discarded_at"))
        batch_op.drop_column("discard_reason")
        batch_op.drop_column("discarded_by_id")
        batch_op.drop_column("discarded_at")
    with op.batch_alter_table("diagnosis_results", schema=None) as batch_op:
        batch_op.alter_column("refer_suggested", new_column_name="auto_refer")
    with op.batch_alter_table("referrals", schema=None) as batch_op:
        batch_op.drop_column("question")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("registration_number", sa.String(length=64), nullable=True))
        batch_op.drop_column("status_reason")
        batch_op.drop_column("requested_role")
