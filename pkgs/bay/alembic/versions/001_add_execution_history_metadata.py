"""Add metadata fields to execution_history table

Revision ID: 001
Create Date: 2025-01-28

This migration adds description, tags, and notes fields to the execution_history
table to support skill library functionality.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add metadata columns to execution_history table."""
    # Add description column
    op.add_column(
        'execution_history',
        sa.Column('description', sa.String(), nullable=True)
    )

    # Add tags column (comma-separated string)
    op.add_column(
        'execution_history',
        sa.Column('tags', sa.String(), nullable=True)
    )

    # Add notes column
    op.add_column(
        'execution_history',
        sa.Column('notes', sa.String(), nullable=True)
    )


def downgrade() -> None:
    """Remove metadata columns from execution_history table."""
    op.drop_column('execution_history', 'notes')
    op.drop_column('execution_history', 'tags')
    op.drop_column('execution_history', 'description')
