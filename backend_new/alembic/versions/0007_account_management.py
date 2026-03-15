"""Add first_name/last_name to users. Add user_tokens table.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(100), nullable=True))

    # Create enum type — safe even if it already exists (e.g. from a partial run).
    op.execute(
        "DO $$ BEGIN "
        "  CREATE TYPE tokentypeenum AS ENUM ('password_reset', 'email_verification'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$;"
    )

    op.execute("""
        CREATE TABLE user_tokens (
            id          UUID        NOT NULL DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL,
            token_hash  VARCHAR(64) NOT NULL,
            token_type  tokentypeenum NOT NULL,
            new_email   VARCHAR(255),
            expires_at  TIMESTAMPTZ NOT NULL,
            used_at     TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            UNIQUE (token_hash),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    op.create_index("ix_user_tokens_token_hash", "user_tokens", ["token_hash"])
    op.create_index("ix_user_tokens_user_id", "user_tokens", ["user_id"])


def downgrade():
    op.drop_index("ix_user_tokens_user_id", table_name="user_tokens")
    op.drop_index("ix_user_tokens_token_hash", table_name="user_tokens")
    op.drop_table("user_tokens")
    op.execute("DROP TYPE IF EXISTS tokentypeenum")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
