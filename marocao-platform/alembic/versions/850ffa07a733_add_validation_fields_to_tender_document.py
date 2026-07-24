"""add_validation_fields_to_tender_document

Revision ID: 850ffa07a733
Revises: fba961c81908
Create Date: 2026-07-24 09:48:21.145935

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '850ffa07a733'
down_revision: Union[str, Sequence[str], None] = 'fba961c81908'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
