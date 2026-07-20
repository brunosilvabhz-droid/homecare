"""company accounts, seats and invitations"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="0021_company_accounts"
down_revision="0020_context_and_exit_survey"
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind();dialect=bind.dialect.name
    inspector=sa.inspect(bind)
    if dialect=="postgresql":
        # PostgreSQL exige que novos valores de ENUM sejam confirmados antes
        # de serem usados pela tabela de convites criada nesta migração.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'COMPANY_ADMIN'")
            op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'COORDINATOR'")
    org_columns={column["name"] for column in inspector.get_columns("organizations")}
    if "account_type" not in org_columns: op.add_column("organizations",sa.Column("account_type",sa.String(20),nullable=False,server_default="individual"))
    if "document" not in org_columns: op.add_column("organizations",sa.Column("document",sa.String(18),nullable=True))
    if "licensed_seats" not in org_columns: op.add_column("organizations",sa.Column("licensed_seats",sa.Integer(),nullable=False,server_default="1"))
    if "ix_organizations_account_type" not in {index["name"] for index in inspector.get_indexes("organizations")}: op.create_index("ix_organizations_account_type","organizations",["account_type"])
    plan_columns={column["name"] for column in inspector.get_columns("plans")}
    if "per_seat" not in plan_columns: op.add_column("plans",sa.Column("per_seat",sa.Boolean(),nullable=False,server_default=sa.false()))
    if "minimum_seats" not in plan_columns: op.add_column("plans",sa.Column("minimum_seats",sa.Integer(),nullable=False,server_default="1"))
    subscription_columns={column["name"] for column in inspector.get_columns("subscriptions")}
    if "pending_licensed_seats" not in subscription_columns: op.add_column("subscriptions",sa.Column("pending_licensed_seats",sa.Integer(),nullable=True))
    role_type=postgresql.ENUM("PROFESSIONAL","FAMILY","ADMIN","COMPANY_ADMIN","COORDINATOR",name="role",create_type=False) if dialect=="postgresql" else sa.Enum("PROFESSIONAL","FAMILY","ADMIN","COMPANY_ADMIN","COORDINATOR",name="role")
    if "company_invitations" not in inspector.get_table_names(): op.create_table("company_invitations",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),
        sa.Column("email",sa.String(255),nullable=False),sa.Column("name",sa.String(120),nullable=False),sa.Column("role",role_type,nullable=False),sa.Column("profession",sa.String(60)),
        sa.Column("token_hash",sa.String(64),nullable=False),sa.Column("invited_by_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("accepted_at",sa.DateTime(timezone=True)),sa.Column("revoked_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    invitation_indexes={index["name"] for index in sa.inspect(bind).get_indexes("company_invitations")}
    if "ix_company_invitations_organization_id" not in invitation_indexes: op.create_index("ix_company_invitations_organization_id","company_invitations",["organization_id"])
    if "ix_company_invitations_email" not in invitation_indexes: op.create_index("ix_company_invitations_email","company_invitations",["email"])
    if "ix_company_invitations_token_hash" not in invitation_indexes: op.create_index("ix_company_invitations_token_hash","company_invitations",["token_hash"],unique=True)
    plans=sa.table("plans",sa.column("id",sa.String),sa.column("code",sa.String),sa.column("name",sa.String),sa.column("monthly_price",sa.Numeric),sa.column("annual_monthly_price",sa.Numeric),sa.column("active",sa.Boolean),sa.column("ai_daily_limit",sa.Integer),sa.column("whatsapp_monthly_limit",sa.Integer),sa.column("per_seat",sa.Boolean),sa.column("minimum_seats",sa.Integer))
    exists=bind.execute(sa.select(plans.c.id).where(plans.c.code=="company")).first()
    if not exists: op.bulk_insert(plans,[{"id":"company-impacto-care-plan-0001","code":"company","name":"Impacto Care Empresarial","monthly_price":25.00,"annual_monthly_price":25.00,"active":True,"ai_daily_limit":20,"whatsapp_monthly_limit":100,"per_seat":True,"minimum_seats":6}])

def downgrade():
    op.execute("DELETE FROM plans WHERE code='company'")
    op.drop_table("company_invitations")
    op.drop_column("subscriptions","pending_licensed_seats")
    op.drop_column("plans","minimum_seats");op.drop_column("plans","per_seat")
    op.drop_index("ix_organizations_account_type",table_name="organizations")
    op.drop_column("organizations","licensed_seats");op.drop_column("organizations","document");op.drop_column("organizations","account_type")
