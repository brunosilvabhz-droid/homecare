"""family assessment intake"""
from alembic import op
import sqlalchemy as sa
revision="0005_family_intake"; down_revision="0004_routes_vehicles"; branch_labels=None; depends_on=None
def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("patients")}
    if "status" not in columns:
        op.add_column("patients",sa.Column("status",sa.String(20),nullable=False,server_default="active"));op.create_index("ix_patients_status","patients",["status"])
    if "intake_requests" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("intake_requests",sa.Column("id",sa.String(36),primary_key=True),sa.Column("created_by_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("token_hash",sa.String(64),nullable=False,unique=True),sa.Column("status",sa.String(20),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("submitted_at",sa.DateTime(timezone=True)),sa.Column("patient_id",sa.String(36),sa.ForeignKey("patients.id")),sa.Column("family_data",sa.JSON()),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_intake_requests_token_hash","intake_requests",["token_hash"],unique=True);op.create_index("ix_intake_requests_status","intake_requests",["status"]);op.create_index("ix_intake_requests_organization_id","intake_requests",["organization_id"])
def downgrade(): op.drop_table("intake_requests");op.drop_column("patients","status")
