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
    inspector=sa.inspect(op.get_bind());subscriptions={c["name"] for c in inspector.get_columns("subscriptions")};visits={c["name"] for c in inspector.get_columns("visits")};finance={c["name"] for c in inspector.get_columns("finance_entries")}
    if "complimentary_until" not in subscriptions:op.add_column("subscriptions",sa.Column("complimentary_until",sa.Date(),nullable=True))
    if "complimentary_note" not in subscriptions:op.add_column("subscriptions",sa.Column("complimentary_note",sa.String(255),nullable=True))
    if "confirmation_manual_sent_at" not in visits:op.add_column("visits",sa.Column("confirmation_manual_sent_at",sa.DateTime(timezone=True),nullable=True))
    if "confirmation_automatic_sent_at" not in visits:op.add_column("visits",sa.Column("confirmation_automatic_sent_at",sa.DateTime(timezone=True),nullable=True))
    if "category" not in finance:op.add_column("finance_entries",sa.Column("category",sa.String(60),nullable=False,server_default="Outros"))
    indexes={index["name"] for index in inspector.get_indexes("finance_entries")}
    if "ix_finance_entries_category" not in indexes:op.create_index("ix_finance_entries_category","finance_entries",["category"])

def downgrade():
    op.drop_index("ix_finance_entries_category",table_name="finance_entries")
    op.drop_column("finance_entries","category")
    op.drop_column("visits","confirmation_automatic_sent_at")
    op.drop_column("visits","confirmation_manual_sent_at")
    op.drop_column("subscriptions","complimentary_note")
    op.drop_column("subscriptions","complimentary_until")
