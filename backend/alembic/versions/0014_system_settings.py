"""administrative system settings"""
from alembic import op
import sqlalchemy as sa
revision="0014_system_settings";down_revision="0013_profile_and_support";branch_labels=None;depends_on=None
def upgrade():
    inspector=sa.inspect(op.get_bind())
    if "system_settings" not in inspector.get_table_names():
        op.create_table("system_settings",sa.Column("id",sa.String(36),primary_key=True),sa.Column("key",sa.String(80),nullable=False),sa.Column("value",sa.JSON(),nullable=False),sa.Column("updated_by_id",sa.String(36),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
        op.create_index("ix_system_settings_key","system_settings",["key"],unique=True)
def downgrade(): op.drop_table("system_settings")
