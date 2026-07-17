"""profile photo and support responses"""
from alembic import op
import sqlalchemy as sa
revision="0013_profile_and_support";down_revision="0012_visit_self_service";branch_labels=None;depends_on=None
def upgrade():
    inspector=sa.inspect(op.get_bind())
    users={c["name"] for c in inspector.get_columns("users")}
    for name,type_ in [("profile_photo",sa.LargeBinary()),("profile_photo_content_type",sa.String(40)),("profile_photo_updated_at",sa.DateTime(timezone=True))]:
        if name not in users: op.add_column("users",sa.Column(name,type_,nullable=True))
    tickets={c["name"] for c in inspector.get_columns("support_tickets")}
    for name,type_ in [("admin_response",sa.Text()),("responded_at",sa.DateTime(timezone=True)),("closed_at",sa.DateTime(timezone=True))]:
        if name not in tickets: op.add_column("support_tickets",sa.Column(name,type_,nullable=True))
def downgrade():
    for name in ["closed_at","responded_at","admin_response"]: op.drop_column("support_tickets",name)
    for name in ["profile_photo_updated_at","profile_photo_content_type","profile_photo"]: op.drop_column("users",name)
