"""suppression PieceDetachee

Retire le champ orphelin `EquipementAttenteReparation.piece_necessaire_id` (jamais câblé côté
frontend, 0 ligne ne l'utilisait — voir SUIVI_PROJET.md) avant de supprimer la table
`pieces_detachees` elle-même. `op.drop_column`/`op.drop_constraint` hors mode batch échouent
sur SQLite (limite déjà rencontrée plusieurs fois sur ce projet) — DROP TABLE simple n'a pas
ce problème.

Revision ID: 6678a1413024
Revises: a103a2b7e8d3
Create Date: 2026-08-17 15:23:16.079152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6678a1413024'
down_revision: Union[str, None] = 'a103a2b7e8d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('equipements_attente_reparation', schema=None) as batch_op:
        batch_op.drop_column('piece_necessaire_id')

    op.drop_index('ix_pieces_detachees_reference', table_name='pieces_detachees')
    op.drop_table('pieces_detachees')


def downgrade() -> None:
    op.create_table('pieces_detachees',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('reference', sa.VARCHAR(length=100), nullable=False),
    sa.Column('nom', sa.VARCHAR(length=255), nullable=False),
    sa.Column('type_equipement_compatible', sa.VARCHAR(length=150), nullable=False),
    sa.Column('quantite_stock', sa.INTEGER(), nullable=False),
    sa.Column('seuil_alerte', sa.INTEGER(), nullable=False),
    sa.Column('fournisseur', sa.VARCHAR(length=255), nullable=False),
    sa.Column('emplacement_stock', sa.VARCHAR(length=100), nullable=True),
    sa.Column('created_at', sa.DATETIME(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_pieces_detachees_reference', 'pieces_detachees', ['reference'], unique=1)

    with op.batch_alter_table('equipements_attente_reparation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('piece_necessaire_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            'fk_equipements_attente_reparation_piece_necessaire_id',
            'pieces_detachees', ['piece_necessaire_id'], ['id'], ondelete='SET NULL',
        )
