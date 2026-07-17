"""contextual messages and exit survey

Revision ID: 0020_context_and_exit_survey
Revises: 0019_onboarding_relationship
"""
from alembic import op
import sqlalchemy as sa
revision="0020_context_and_exit_survey";down_revision="0019_onboarding_relationship";branch_labels=None;depends_on=None
def upgrade():
    op.create_table("context_message_interactions",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),nullable=False),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("message_code",sa.String(80),nullable=False),sa.Column("views",sa.Integer(),nullable=False),sa.Column("last_viewed_at",sa.DateTime(timezone=True)),sa.Column("clicked_at",sa.DateTime(timezone=True)),sa.Column("dismissed_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("user_id","message_code",name="uq_context_message_user"));op.create_index("ix_context_message_user","context_message_interactions",["user_id"])
    op.create_table("exit_survey_responses",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),nullable=False),sa.Column("user_id",sa.String(36),nullable=False),sa.Column("subscription_id",sa.String(36),nullable=False),sa.Column("reason",sa.String(60),nullable=False),sa.Column("details",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("user_id","subscription_id",name="uq_exit_survey_cycle"));op.create_index("ix_exit_survey_reason","exit_survey_responses",["reason"])
def downgrade():op.drop_table("exit_survey_responses");op.drop_table("context_message_interactions")
