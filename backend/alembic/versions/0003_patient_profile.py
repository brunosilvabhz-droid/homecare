"""complete patient profile"""
from alembic import op
import sqlalchemy as sa
revision="0003_patient_profile"; down_revision="0002_professional_email_verification"; branch_labels=None; depends_on=None
def upgrade():
    columns=[("cpf",sa.String(14)),("gender",sa.String(30)),("email",sa.String(255)),("postal_code",sa.String(9)),("address_number",sa.String(20)),("address_complement",sa.String(100)),("neighborhood",sa.String(100)),("city",sa.String(100)),("state",sa.String(2))]
    existing={column["name"] for column in sa.inspect(op.get_bind()).get_columns("patients")}
    for name,type_ in columns:
        if name not in existing: op.add_column("patients",sa.Column(name,type_,nullable=True))
def downgrade():
    existing={column["name"] for column in sa.inspect(op.get_bind()).get_columns("patients")}
    for name in ["state","city","neighborhood","address_complement","address_number","postal_code","email","gender","cpf"]:
        if name in existing: op.drop_column("patients",name)
