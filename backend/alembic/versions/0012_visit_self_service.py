"""visit self service, availability and vital signs

Revision ID: 0012_visit_self_service
Revises: 0011_user_last_login
"""
from alembic import op
import sqlalchemy as sa

revision="0012_visit_self_service";down_revision="0011_user_last_login";branch_labels=None;depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind());tables=set(inspector.get_table_names())
    if "default_session_duration_minutes" not in {c["name"] for c in inspector.get_columns("users")}: op.add_column("users",sa.Column("default_session_duration_minutes",sa.Integer(),nullable=False,server_default="60"))
    if "professional_availabilities" not in tables:
        op.create_table("professional_availabilities",sa.Column("id",sa.String(36),primary_key=True),sa.Column("professional_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("weekday",sa.Integer(),nullable=False),sa.Column("start_time",sa.Time(),nullable=False),sa.Column("end_time",sa.Time(),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
        op.create_index("ix_professional_availabilities_professional_id","professional_availabilities",["professional_id"]);op.create_index("ix_professional_availabilities_organization_id","professional_availabilities",["organization_id"]);op.create_index("ix_professional_availabilities_weekday","professional_availabilities",["weekday"])
    visit_columns={c["name"] for c in inspector.get_columns("visits")}
    for name,type_ in [("confirmation_token_hash",sa.String(64)),("patient_response",sa.String(20)),("patient_responded_at",sa.DateTime(timezone=True))]:
        if name not in visit_columns: op.add_column("visits",sa.Column(name,type_,nullable=True))
    if "confirmation_token_hash" not in visit_columns: op.create_index("ix_visits_confirmation_token_hash","visits",["confirmation_token_hash"],unique=True)
    record_columns={c["name"] for c in inspector.get_columns("service_records")}
    for name,type_ in [("weight_kg",sa.Numeric(6,2)),("blood_pressure_systolic",sa.Integer()),("blood_pressure_diastolic",sa.Integer()),("heart_rate_bpm",sa.Integer()),("respiratory_rate_bpm",sa.Integer()),("temperature_c",sa.Numeric(4,1)),("oxygen_saturation_percent",sa.Integer()),("blood_glucose_mg_dl",sa.Integer())]:
        if name not in record_columns: op.add_column("service_records",sa.Column(name,type_,nullable=True))

def downgrade():
    for name in ["blood_glucose_mg_dl","oxygen_saturation_percent","temperature_c","respiratory_rate_bpm","heart_rate_bpm","blood_pressure_diastolic","blood_pressure_systolic","weight_kg"]: op.drop_column("service_records",name)
    op.drop_index("ix_visits_confirmation_token_hash",table_name="visits")
    for name in ["patient_responded_at","patient_response","confirmation_token_hash"]: op.drop_column("visits",name)
    op.drop_table("professional_availabilities");op.drop_column("users","default_session_duration_minutes")
