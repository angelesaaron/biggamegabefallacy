"""Replace users.tier with users.is_subscriber.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column(
        "is_subscriber", sa.Boolean(), nullable=False, server_default="true"
    ))
    op.drop_column("users", "tier")

def downgrade():
    op.add_column("users", sa.Column(
        "tier", sa.String(20), nullable=False, server_default="free"
    ))
    op.drop_column("users", "is_subscriber")
