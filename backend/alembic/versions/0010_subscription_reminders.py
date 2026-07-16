"""subscription expiration reminders

Revision ID: 0010_subscription_reminders
Revises: 0009_support_tickets
"""
from alembic import op
import sqlalchemy as sa
revision="0010_subscription_reminders";down_revision="0009_support_tickets";branch_labels=None;depends_on=None
def upgrade():
    if "subscription_reminders" in sa.inspect(op.get_bind()).get_table_names(): return
    op.create_table("subscription_reminders",sa.Column("id",sa.String(36),nullable=False),sa.Column("subscription_id",sa.String(36),nullable=False),sa.Column("reminder_key",sa.String(120),nullable=False),sa.Column("reminder_type",sa.String(30),nullable=False),sa.Column("sent_at",sa.DateTime(timezone=True),nullable=False),sa.ForeignKeyConstraint(["subscription_id"],["subscriptions.id"]),sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("reminder_key"))
    op.create_index(op.f("ix_subscription_reminders_subscription_id"),"subscription_reminders",["subscription_id"],unique=False)
    op.create_index(op.f("ix_subscription_reminders_reminder_key"),"subscription_reminders",["reminder_key"],unique=True)
    op.create_index(op.f("ix_subscription_reminders_reminder_type"),"subscription_reminders",["reminder_type"],unique=False)
def downgrade():
    if "subscription_reminders" in sa.inspect(op.get_bind()).get_table_names(): op.drop_table("subscription_reminders")
