"""add cookidoo_sync_error

Revision ID: b7f2c1d4e8a9
Revises: a359ecd6a941
Create Date: 2026-07-15 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f2c1d4e8a9'
down_revision = 'a359ecd6a941'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'recipe',
        sa.Column('cookidoo_sync_error', sa.Boolean(), nullable=False,
                  server_default='false'),
    )


def downgrade():
    op.drop_column('recipe', 'cookidoo_sync_error')
