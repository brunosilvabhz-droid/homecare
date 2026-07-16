"""management improvements"""
from alembic import op
import sqlalchemy as sa

revision = "0007_management_improvements"
down_revision = "0006_asaas_billing"
branch_labels = None
depends_on = None

def upgrade():
    patient_columns = {
        "conditions": sa.Text(), "medications": sa.Text(), "allergies": sa.Text(),
        "care_needs": sa.Text(), "mobility": sa.Text(),
        "session_value": sa.Numeric(12, 2), "session_count": sa.Integer(),
    }
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("patients")}
    for name, type_ in patient_columns.items():
        if name not in existing: op.add_column("patients", sa.Column(name, type_, nullable=True))
    intake_existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("intake_requests")}
    if "recipient_name" not in intake_existing: op.add_column("intake_requests", sa.Column("recipient_name", sa.String(120), nullable=True))
    if "recipient_phone" not in intake_existing: op.add_column("intake_requests", sa.Column("recipient_phone", sa.String(30), nullable=True))
    finance_existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("finance_entries")}
    if "entry_type" not in finance_existing: op.add_column("finance_entries", sa.Column("entry_type", sa.String(20), nullable=False, server_default="income"))
    if "source" not in finance_existing: op.add_column("finance_entries", sa.Column("source", sa.String(40), nullable=True))

def downgrade():
    for table, columns in [
        ("finance_entries", ["source", "entry_type"]),
        ("intake_requests", ["recipient_phone", "recipient_name"]),
        ("patients", ["session_count", "session_value", "mobility", "care_needs", "allergies", "medications", "conditions"]),
    ]:
        existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
        for column in columns:
            if column in existing: op.drop_column(table, column)
