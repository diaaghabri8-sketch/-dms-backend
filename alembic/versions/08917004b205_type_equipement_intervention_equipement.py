"""type equipement intervention equipement

Revision ID: 08917004b205
Revises: e500f49432a4
Create Date: 2026-08-18 01:20:47.322752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08917004b205'
down_revision: Union[str, None] = 'e500f49432a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('intervention_equipements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type_equipement', sa.String(length=150), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('intervention_equipements', schema=None) as batch_op:
        batch_op.drop_column('type_equipement')
