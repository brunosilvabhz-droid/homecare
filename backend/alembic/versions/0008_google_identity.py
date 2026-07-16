"""google identity linkage

Revision ID: 0008_google_identity
Revises: 0007_management_improvements
"""
from alembic import op
import sqlalchemy as sa

revision="0008_google_identity"
down_revision="0007_management_improvements"
branch_labels=None
depends_on=None

def upgrade():
    if "google_identities" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "google_identities",
        sa.Column("id",sa.String(length=36),nullable=False),
        sa.Column("user_id",sa.String(length=36),nullable=False),
        sa.Column("subject",sa.String(length=255),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(["user_id"],["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("subject"),
    )
    op.create_index(op.f("ix_google_identities_user_id"),"google_identities",["user_id"],unique=True)
    op.create_index(op.f("ix_google_identities_subject"),"google_identities",["subject"],unique=True)

def downgrade():
    if "google_identities" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index(op.f("ix_google_identities_subject"),table_name="google_identities")
    op.drop_index(op.f("ix_google_identities_user_id"),table_name="google_identities")
    op.drop_table("google_identities")
