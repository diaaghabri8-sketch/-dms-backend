"""suppression EquipementNeufAVendre

Retire `InterventionEquipement.equipement_vente_id` (3e source polymorphe du modèle
équipement d'intervention, jamais écrite par aucun formulaire actuel, 0 ligne ne l'utilisait
— voir SUIVI_PROJET.md) avant de supprimer la table `equipements_neuf_a_vendre` elle-même.
Mode batch requis sur SQLite pour drop_column/drop_constraint (limite déjà rencontrée
plusieurs fois sur ce projet) — DROP TABLE simple n'a pas ce problème.

Revision ID: 873b0b77d5dd
Revises: 6678a1413024
Create Date: 2026-08-17 15:39:01.083651

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '873b0b77d5dd'
down_revision: Union[str, None] = '6678a1413024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('intervention_equipements', schema=None) as batch_op:
        batch_op.drop_column('equipement_vente_id')

    op.drop_index('ix_equipements_neuf_a_vendre_numero_serie', table_name='equipements_neuf_a_vendre')
    op.drop_table('equipements_neuf_a_vendre')

    # Sur Postgres, DROP TABLE ne supprime pas le type ENUM natif associé à la colonne `statut`
    # (`statut_vente`, créé par la migration 320d855d5ad4) — laissé orphelin sinon (ajouté le
    # 2026-09-24, migration Postgres/Supabase, sans effet sur SQLite qui n'a pas de vrai type).
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS statut_vente"))


def downgrade() -> None:
    op.create_table('equipements_neuf_a_vendre',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('numero_serie', sa.VARCHAR(length=100), nullable=False),
    sa.Column('nom', sa.VARCHAR(length=255), nullable=False),
    sa.Column('marque', sa.VARCHAR(length=150), nullable=False),
    sa.Column('type_equipement', sa.VARCHAR(length=150), nullable=False),
    sa.Column('prix', sa.FLOAT(), nullable=True),
    sa.Column('quantite_disponible', sa.INTEGER(), nullable=False),
    sa.Column('statut', sa.VARCHAR(length=10), nullable=False),
    sa.Column('date_reception', sa.DATE(), nullable=False),
    sa.Column('fournisseur', sa.VARCHAR(length=255), nullable=True),
    sa.Column('description', sa.TEXT(), nullable=True),
    sa.Column('created_at', sa.DATETIME(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_equipements_neuf_a_vendre_numero_serie', 'equipements_neuf_a_vendre', ['numero_serie'], unique=1)

    with op.batch_alter_table('intervention_equipements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('equipement_vente_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            'fk_intervention_equipements_equipement_vente_id',
            'equipements_neuf_a_vendre', ['equipement_vente_id'], ['id'],
        )
