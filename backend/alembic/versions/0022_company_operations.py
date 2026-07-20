"""company schedules, attendance and shift handoffs"""
from alembic import op
import sqlalchemy as sa

revision="0022_company_operations"
down_revision="0021_company_accounts"
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind();tables=sa.inspect(bind).get_table_names()
    if "work_attendances" not in tables:
        op.create_table("work_attendances",
            sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("visit_id",sa.String(36),sa.ForeignKey("visits.id"),nullable=False),sa.Column("professional_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
            sa.Column("check_in_at",sa.DateTime(timezone=True),nullable=False),sa.Column("check_in_latitude",sa.Float(),nullable=False),sa.Column("check_in_longitude",sa.Float(),nullable=False),sa.Column("check_in_accuracy_meters",sa.Float()),sa.Column("check_in_distance_meters",sa.Float()),sa.Column("location_verified",sa.Boolean(),nullable=False,server_default=sa.false()),
            sa.Column("check_out_at",sa.DateTime(timezone=True)),sa.Column("check_out_latitude",sa.Float()),sa.Column("check_out_longitude",sa.Float()),sa.Column("check_out_accuracy_meters",sa.Float()),sa.Column("notes",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("visit_id",name="uq_work_attendance_visit"))
        op.create_index("ix_work_attendances_organization_id","work_attendances",["organization_id"]);op.create_index("ix_work_attendances_visit_id","work_attendances",["visit_id"]);op.create_index("ix_work_attendances_professional_id","work_attendances",["professional_id"])
    if "shift_handoffs" not in tables:
        op.create_table("shift_handoffs",
            sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("visit_id",sa.String(36),sa.ForeignKey("visits.id"),nullable=False),sa.Column("patient_id",sa.String(36),sa.ForeignKey("patients.id"),nullable=False),sa.Column("professional_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
            sa.Column("condition_summary",sa.Text(),nullable=False),sa.Column("procedures",sa.Text()),sa.Column("medications",sa.Text()),sa.Column("occurrences",sa.Text()),sa.Column("pending_items",sa.Text()),sa.Column("next_shift_guidance",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("visit_id",name="uq_shift_handoff_visit"))
        op.create_index("ix_shift_handoffs_organization_id","shift_handoffs",["organization_id"]);op.create_index("ix_shift_handoffs_visit_id","shift_handoffs",["visit_id"]);op.create_index("ix_shift_handoffs_patient_id","shift_handoffs",["patient_id"]);op.create_index("ix_shift_handoffs_professional_id","shift_handoffs",["professional_id"])

def downgrade():
    op.drop_table("shift_handoffs");op.drop_table("work_attendances")
