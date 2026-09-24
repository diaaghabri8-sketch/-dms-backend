"""lien parc equipements vers intervention

Revision ID: 98e1027581c3
Revises: d567127f4981
Create Date: 2026-08-14 20:27:00.874759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98e1027581c3'
down_revision: Union[str, None] = 'd567127f4981'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite ne supporte pas ALTER TABLE ADD CONSTRAINT directement (create_foreign_key hors
    # batch) — même limite déjà rencontrée sur la migration des équipements multiples, même
    # solution : batch_alter_table (copy-and-swap).
    with op.batch_alter_table('equipements_attente_reparation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('intervention_equipement_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_equipements_attente_reparation_intervention_equipement_id',
            'intervention_equipements',
            ['intervention_equipement_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('equipements_attente_reparation', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_equipements_attente_reparation_intervention_equipement_id', type_='foreignkey'
        )
        batch_op.drop_column('intervention_equipement_id')
