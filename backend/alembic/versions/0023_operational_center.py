"""operational center handoff reads"""
from alembic import op
import sqlalchemy as sa

revision="0023_operational_center"
down_revision="0022_company_operations"
branch_labels=None
depends_on=None

def upgrade():
    if "handoff_reads" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("handoff_reads",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("handoff_id",sa.String(36),sa.ForeignKey("shift_handoffs.id"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("read_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("handoff_id","user_id",name="uq_handoff_read_user"))
        op.create_index("ix_handoff_reads_organization_id","handoff_reads",["organization_id"]);op.create_index("ix_handoff_reads_handoff_id","handoff_reads",["handoff_id"]);op.create_index("ix_handoff_reads_user_id","handoff_reads",["user_id"])

def downgrade(): op.drop_table("handoff_reads")
