"""specialty routing, automatic queueing of uncertain cases, new-decision flag

* users.specialties: which conditions a specialist reviews (JSON list; "general" matches every case).
* referrals.conditions: what the health worker's question is about.
* referrals.priority: urgent or routine (default from the risk policy, the health worker may change it; sets the
  24 h / 72 h review target).
  Existing rows get the rule used before: urgent when the reason was "positive", else routine.
* referrals.assigned_to_id / assigned_at: the specialist who took the case.
* referrals.queued_automatically: the risk policy queued an uncertain case (as in the proposal's sequence diagram).
* screenings.new_decision: a specialist decision the health worker has not opened yet.

Revision ID: c4e8a2f61b37
Revises: 7a3c5e9b1d20
Create Date: 2026-10-28 14:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.core.database  # noqa: F401  (custom UTCDateTime column type)

revision: str = "c4e8a2f61b37"
down_revision: Union[str, Sequence[str], None] = "7a3c5e9b1d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PRIORITY = sa.Enum("urgent", "routine", name="reviewpriority", native_enum=False, length=32)


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("specialties", sa.JSON(), nullable=True))
    with op.batch_alter_table("referrals") as batch_op:
        batch_op.add_column(sa.Column("conditions", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("queued_automatically", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("priority", _PRIORITY, nullable=False, server_default="routine"))
        batch_op.add_column(sa.Column("assigned_to_id", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("assigned_at", app.core.database.UTCDateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_referrals_assigned_to_id"), ["assigned_to_id"], unique=False)
        batch_op.create_foreign_key("fk_referrals_assigned_to_id_users", "users", ["assigned_to_id"], ["id"],
                                    ondelete="SET NULL")
    with op.batch_alter_table("screenings") as batch_op:
        batch_op.add_column(sa.Column("new_decision", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE referrals SET priority = 'urgent' WHERE reason = 'positive'")
    op.execute("UPDATE users SET specialties = '[]' WHERE specialties IS NULL")
    op.execute("UPDATE referrals SET conditions = '[]' WHERE conditions IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("screenings") as batch_op:
        batch_op.drop_column("new_decision")
    with op.batch_alter_table("referrals") as batch_op:
        batch_op.drop_column("queued_automatically")
        batch_op.drop_constraint("fk_referrals_assigned_to_id_users", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_referrals_assigned_to_id"))
        batch_op.drop_column("assigned_at")
        batch_op.drop_column("assigned_to_id")
        batch_op.drop_column("priority")
        batch_op.drop_column("conditions")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("specialties")
