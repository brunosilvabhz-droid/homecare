"""professional profile and email verification"""
from alembic import op
import sqlalchemy as sa
revision="0002_professional_email_verification"; down_revision="0001_initial"; branch_labels=None; depends_on=None
def upgrade():
    # Alembic creates version_num as VARCHAR(32), but this project uses
    # descriptive revision identifiers that can be longer than 32 characters.
    # PostgreSQL enforces that limit (SQLite does not), so widen the column
    # before Alembic records this revision at the end of the transaction.
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
    columns=[("email_verified_at",sa.DateTime(timezone=True)),("phone",sa.String(30)),("cpf",sa.String(14)),("profession",sa.String(60)),("profession_other",sa.String(100)),("council_name",sa.String(30)),("council_code",sa.String(40)),("council_state",sa.String(2)),("postal_code",sa.String(9)),("address",sa.String(255)),("address_number",sa.String(20)),("address_complement",sa.String(100)),("neighborhood",sa.String(100)),("city",sa.String(100)),("state",sa.String(2))]
    existing={column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    for name,type_ in columns:
        if name not in existing: op.add_column("users",sa.Column(name,type_,nullable=True))
    op.execute("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP")
def downgrade():
    existing={column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    for name in ["state","city","neighborhood","address_complement","address_number","address","postal_code","council_state","council_code","council_name","profession_other","profession","cpf","phone","email_verified_at"]:
        if name in existing: op.drop_column("users",name)
