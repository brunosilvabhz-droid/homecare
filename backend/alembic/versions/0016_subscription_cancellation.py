"""subscription cancellation scheduling"""
from alembic import op
import sqlalchemy as sa
revision="0016_subscription_cancellation";down_revision="0015_professional_profile_signature";branch_labels=None;depends_on=None
def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("subscriptions")}
    if "cancel_at_period_end" not in columns: op.add_column("subscriptions",sa.Column("cancel_at_period_end",sa.Boolean(),nullable=False,server_default=sa.false()))
    if "cancellation_requested_at" not in columns: op.add_column("subscriptions",sa.Column("cancellation_requested_at",sa.DateTime(timezone=True),nullable=True))
def downgrade():
    op.drop_column("subscriptions","cancellation_requested_at");op.drop_column("subscriptions","cancel_at_period_end")
