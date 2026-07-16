"""track user last login

Revision ID: 0011_user_last_login
Revises: 0010_subscription_reminders
"""
from alembic import op
import sqlalchemy as sa

revision="0011_user_last_login";down_revision="0010_subscription_reminders";branch_labels=None;depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "last_login_at" not in columns:
        op.add_column("users",sa.Column("last_login_at",sa.DateTime(timezone=True),nullable=True))

def downgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "last_login_at" in columns:
        op.drop_column("users","last_login_at")
