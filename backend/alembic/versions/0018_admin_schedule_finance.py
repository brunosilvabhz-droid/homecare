"""admin partnerships, confirmation tracking and finance categories

Revision ID: 0018_admin_schedule_finance
Revises: 0017_ai_whatsapp_premium
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_admin_schedule_finance"
down_revision = "0017_ai_whatsapp_premium"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("subscriptions",sa.Column("complimentary_until",sa.Date(),nullable=True))
    op.add_column("subscriptions",sa.Column("complimentary_note",sa.String(255),nullable=True))
    op.add_column("visits",sa.Column("confirmation_manual_sent_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("visits",sa.Column("confirmation_automatic_sent_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("finance_entries",sa.Column("category",sa.String(60),nullable=False,server_default="Outros"))
    op.create_index("ix_finance_entries_category","finance_entries",["category"])

def downgrade():
    op.drop_index("ix_finance_entries_category",table_name="finance_entries")
    op.drop_column("finance_entries","category")
    op.drop_column("visits","confirmation_automatic_sent_at")
    op.drop_column("visits","confirmation_manual_sent_at")
    op.drop_column("subscriptions","complimentary_note")
    op.drop_column("subscriptions","complimentary_until")
