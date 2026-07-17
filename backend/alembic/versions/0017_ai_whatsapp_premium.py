"""AI assistant, WhatsApp automation and premium plan"""
from alembic import op
import sqlalchemy as sa
revision="0017_ai_whatsapp_premium";down_revision="0016_subscription_cancellation";branch_labels=None;depends_on=None
def upgrade():
    bind=op.get_bind();inspector=sa.inspect(bind);plan_columns={c["name"] for c in inspector.get_columns("plans")}
    if "ai_daily_limit" not in plan_columns: op.add_column("plans",sa.Column("ai_daily_limit",sa.Integer(),nullable=False,server_default="10"))
    if "whatsapp_monthly_limit" not in plan_columns: op.add_column("plans",sa.Column("whatsapp_monthly_limit",sa.Integer(),nullable=False,server_default="0"))
    subscription_columns={c["name"] for c in inspector.get_columns("subscriptions")}
    if "pending_plan_id" not in subscription_columns: op.add_column("subscriptions",sa.Column("pending_plan_id",sa.String(36),sa.ForeignKey("plans.id"),nullable=True))
    op.create_table("ai_analyses",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False,index=True),sa.Column("visit_id",sa.String(36),sa.ForeignKey("visits.id"),nullable=False,index=True),sa.Column("patient_id",sa.String(36),sa.ForeignKey("patients.id"),nullable=False,index=True),sa.Column("professional_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False,index=True),sa.Column("analysis_type",sa.String(20),nullable=False,index=True),sa.Column("content",sa.JSON(),nullable=False),sa.Column("model",sa.String(80),nullable=False),sa.Column("input_tokens",sa.Integer()),sa.Column("output_tokens",sa.Integer()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("visit_id","analysis_type",name="uq_ai_visit_type"))
    op.create_table("whatsapp_confirmations",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False,index=True),sa.Column("visit_id",sa.String(36),sa.ForeignKey("visits.id"),nullable=False,unique=True,index=True),sa.Column("status",sa.String(20),nullable=False,index=True),sa.Column("attempts",sa.Integer(),nullable=False,server_default="0"),sa.Column("provider_message_id",sa.String(160)),sa.Column("sent_at",sa.DateTime(timezone=True)),sa.Column("error_message",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    plans=sa.table("plans",sa.column("id",sa.String),sa.column("code",sa.String),sa.column("name",sa.String),sa.column("monthly_price",sa.Numeric),sa.column("annual_monthly_price",sa.Numeric),sa.column("active",sa.Boolean),sa.column("ai_daily_limit",sa.Integer),sa.column("whatsapp_monthly_limit",sa.Integer))
    op.execute(plans.update().where(plans.c.code=="pro").values(ai_daily_limit=10,whatsapp_monthly_limit=0))
    exists=bind.execute(sa.select(plans.c.id).where(plans.c.code=="premium")).first()
    if not exists: op.bulk_insert(plans,[{"id":"premium-impacto-care-plan-000001","code":"premium","name":"Impacto Care Premium","monthly_price":79.90,"annual_monthly_price":59.90,"active":True,"ai_daily_limit":20,"whatsapp_monthly_limit":100}])
def downgrade():
    op.drop_table("whatsapp_confirmations");op.drop_table("ai_analyses");op.drop_column("subscriptions","pending_plan_id");op.drop_column("plans","whatsapp_monthly_limit");op.drop_column("plans","ai_daily_limit")
