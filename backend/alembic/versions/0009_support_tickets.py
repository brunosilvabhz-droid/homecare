"""support tickets

Revision ID: 0009_support_tickets
Revises: 0008_google_identity
"""
from alembic import op
import sqlalchemy as sa

revision="0009_support_tickets"
down_revision="0008_google_identity"
branch_labels=None
depends_on=None

def upgrade():
    if "support_tickets" in sa.inspect(op.get_bind()).get_table_names(): return
    op.create_table("support_tickets",
        sa.Column("id",sa.String(36),nullable=False),
        sa.Column("ticket_number",sa.String(30),nullable=False),
        sa.Column("user_id",sa.String(36),nullable=False),
        sa.Column("category",sa.String(30),nullable=False),
        sa.Column("description",sa.Text(),nullable=False),
        sa.Column("status",sa.String(20),nullable=False),
        sa.Column("email_sent_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("organization_id",sa.String(36),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(["organization_id"],["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"],["users.id"]),
        sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("ticket_number"))
    op.create_index(op.f("ix_support_tickets_ticket_number"),"support_tickets",["ticket_number"],unique=True)
    op.create_index(op.f("ix_support_tickets_user_id"),"support_tickets",["user_id"],unique=False)
    op.create_index(op.f("ix_support_tickets_category"),"support_tickets",["category"],unique=False)
    op.create_index(op.f("ix_support_tickets_status"),"support_tickets",["status"],unique=False)
    op.create_index(op.f("ix_support_tickets_organization_id"),"support_tickets",["organization_id"],unique=False)

def downgrade():
    if "support_tickets" not in sa.inspect(op.get_bind()).get_table_names(): return
    op.drop_table("support_tickets")
