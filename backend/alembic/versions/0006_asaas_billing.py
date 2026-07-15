"""asaas checkout and webhook events"""
from alembic import op
import sqlalchemy as sa
revision="0006_asaas_billing"; down_revision="0005_family_intake"; branch_labels=None; depends_on=None
def upgrade():
    if "billing_webhook_events" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("billing_webhook_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("gateway",sa.String(30),nullable=False),sa.Column("event_id",sa.String(160),nullable=False),sa.Column("event_type",sa.String(80),nullable=False),sa.Column("payload",sa.JSON(),nullable=False),sa.Column("processed_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_billing_webhook_events_event_id","billing_webhook_events",["event_id"],unique=True)
    if op.get_bind().dialect.name=="sqlite": op.execute("UPDATE subscriptions SET current_period_end = date('now', '+30 day') WHERE status = 'TRIAL' AND current_period_end IS NULL")
    else: op.execute("UPDATE subscriptions SET current_period_end = CURRENT_DATE + 30 WHERE status = 'TRIAL' AND current_period_end IS NULL")
def downgrade(): op.drop_table("billing_webhook_events")
