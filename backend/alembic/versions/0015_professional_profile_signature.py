"""professional profile and record signature snapshots"""
from alembic import op
import sqlalchemy as sa
revision="0015_professional_profile_signature";down_revision="0014_system_settings";branch_labels=None;depends_on=None
def upgrade():
    inspector=sa.inspect(op.get_bind());users={c["name"] for c in inspector.get_columns("users")}
    for name,type_ in [("professional_summary",sa.Text()),("specialties",sa.Text()),("education",sa.Text()),("experience_years",sa.Integer()),("service_areas",sa.Text()),("professional_approach",sa.Text()),("signature_name",sa.String(120)),("signature_council",sa.String(100)),("signature_profession",sa.String(100))]:
        if name not in users: op.add_column("users",sa.Column(name,type_,nullable=True))
    records={c["name"] for c in inspector.get_columns("service_records")}
    for name in ["professional_signature_name","professional_signature_council","professional_signature_profession"]:
        if name not in records: op.add_column("service_records",sa.Column(name,sa.String(120 if name.endswith("name") else 100),nullable=True))
def downgrade():
    for name in ["professional_signature_profession","professional_signature_council","professional_signature_name"]: op.drop_column("service_records",name)
    for name in ["signature_profession","signature_council","signature_name","professional_approach","service_areas","experience_years","education","specialties","professional_summary"]: op.drop_column("users",name)
