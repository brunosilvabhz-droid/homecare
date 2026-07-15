"""routes and vehicles"""
from alembic import op
import sqlalchemy as sa
revision="0004_routes_vehicles"; down_revision="0003_patient_profile"; branch_labels=None; depends_on=None
def upgrade():
    existing={column["name"] for column in sa.inspect(op.get_bind()).get_columns("patients")}
    for name in ["latitude","longitude"]:
        if name not in existing: op.add_column("patients",sa.Column(name,sa.Float(),nullable=True))
    if "vehicles" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("vehicles",sa.Column("id",sa.String(36),primary_key=True),sa.Column("name",sa.String(100),nullable=False),sa.Column("fuel_type",sa.String(30),nullable=False),sa.Column("average_km_per_liter",sa.Numeric(8,2),nullable=False),sa.Column("fuel_price",sa.Numeric(8,2),nullable=False),sa.Column("additional_cost_per_km",sa.Numeric(8,2),nullable=False),sa.Column("is_default",sa.Boolean(),nullable=False),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
        op.create_index("ix_vehicles_organization_id","vehicles",["organization_id"])
def downgrade():
    if "vehicles" in sa.inspect(op.get_bind()).get_table_names(): op.drop_table("vehicles")
    for name in ["longitude","latitude"]: op.drop_column("patients",name)
