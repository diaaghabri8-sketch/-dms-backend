"""intervention photos internes

Revision ID: 1f117f911d7b
Revises: 08917004b205
Create Date: 2026-08-18 17:31:47.508410

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f117f911d7b'
down_revision: Union[str, None] = '08917004b205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('intervention_photos',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('intervention_id', sa.String(length=20), nullable=False),
    sa.Column('chemin_photo', sa.String(length=500), nullable=False),
    sa.Column('ajoutee_par_id', sa.Integer(), nullable=False),
    sa.Column('ajoutee_le', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['ajoutee_par_id'], ['techniciens.id'], ),
    sa.ForeignKeyConstraint(['intervention_id'], ['interventions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('intervention_photos')
