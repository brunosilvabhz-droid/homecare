"""onboarding, product events and relationship automation

Revision ID: 0019_onboarding_relationship
Revises: 0018_admin_schedule_finance
"""
from alembic import op
import sqlalchemy as sa

revision="0019_onboarding_relationship"; down_revision="0018_admin_schedule_finance"; branch_labels=None; depends_on=None
def upgrade():
    for name in ("first_access_at","first_patient_at","first_schedule_at","first_record_at","activated_at","first_paid_at"):
        op.add_column("users",sa.Column(name,sa.DateTime(timezone=True),nullable=True))
    op.add_column("users",sa.Column("registration_source",sa.String(40),nullable=True))
    for name,default in (("email_operational",True),("email_guidance",True),("email_billing",True),("email_marketing",False),("whatsapp_allowed",False)):
        op.add_column("users",sa.Column(name,sa.Boolean(),nullable=False,server_default=sa.true() if default else sa.false()))
    op.add_column("users",sa.Column("communication_consent_at",sa.DateTime(timezone=True),nullable=True));op.add_column("users",sa.Column("communication_consent_source",sa.String(40),nullable=True));op.add_column("users",sa.Column("communication_consent_version",sa.String(20),nullable=True))
    op.create_table("product_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),nullable=False),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("event_name",sa.String(80),nullable=False),sa.Column("source",sa.String(40),nullable=False),sa.Column("metadata_json",sa.JSON(),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_product_events_org","product_events",["organization_id"]);op.create_index("ix_product_events_user","product_events",["user_id"]);op.create_index("ix_product_events_name","product_events",["event_name"])
    op.create_table("communication_automations",sa.Column("id",sa.String(36),primary_key=True),sa.Column("code",sa.String(80),nullable=False,unique=True),sa.Column("name",sa.String(120),nullable=False),sa.Column("channel",sa.String(20),nullable=False),sa.Column("trigger_type",sa.String(50),nullable=False),sa.Column("offset_days",sa.Integer(),nullable=False),sa.Column("subject",sa.String(180)),sa.Column("content",sa.Text(),nullable=False),sa.Column("action_path",sa.String(180)),sa.Column("is_active",sa.Boolean(),nullable=False),sa.Column("promotional",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("communication_logs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),nullable=False),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("automation_id",sa.String(36),sa.ForeignKey("communication_automations.id")),sa.Column("channel",sa.String(20),nullable=False),sa.Column("template_code",sa.String(80),nullable=False),sa.Column("idempotency_key",sa.String(220),nullable=False,unique=True),sa.Column("scheduled_at",sa.DateTime(timezone=True)),sa.Column("attempted_at",sa.DateTime(timezone=True)),sa.Column("sent_at",sa.DateTime(timezone=True)),sa.Column("status",sa.String(30),nullable=False),sa.Column("provider_id",sa.String(180)),sa.Column("attempts",sa.Integer(),nullable=False),sa.Column("error_message",sa.Text()),sa.Column("skip_reason",sa.String(255)),sa.Column("clicked_at",sa.DateTime(timezone=True)),sa.Column("clicked_url",sa.String(500)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False));op.create_index("ix_communication_logs_org","communication_logs",["organization_id"]);op.create_index("ix_communication_logs_user","communication_logs",["user_id"]);op.create_index("ix_communication_logs_status","communication_logs",["status"])
def downgrade():
    op.drop_table("communication_logs");op.drop_table("communication_automations");op.drop_table("product_events")
    for name in ("communication_consent_version","communication_consent_source","communication_consent_at","whatsapp_allowed","email_marketing","email_billing","email_guidance","email_operational","registration_source","first_paid_at","activated_at","first_record_at","first_schedule_at","first_patient_at","first_access_at"): op.drop_column("users",name)
