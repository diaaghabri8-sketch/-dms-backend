"""vidage pieces detachees et retrait prix

Migration B du chantier "pièces de rechange en texte libre" (voir SUIVI_PROJET.md) — doit
s'exécuter après A (d52198a7682f), qui a déjà recopié le nom de chaque pièce catalogue dans
PieceNecessaire.description_libre. Le catalogue PieceDetachee peut donc être vidé sans risque
de perte d'historique : plus aucune ligne PieceNecessaire n'y fait référence. Le catalogue
lui-même n'est pas supprimé (modèle/table conservés) — il redevient un pur outil de suivi de
stock (quantité, seuil, fournisseur, emplacement), sans prix et sans lien avec les
interventions.

Revision ID: a103a2b7e8d3
Revises: d52198a7682f
Create Date: 2026-08-15 12:52:45.130654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a103a2b7e8d3'
down_revision: Union[str, None] = 'd52198a7682f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM pieces_detachees")

    with op.batch_alter_table('pieces_detachees', schema=None) as batch_op:
        batch_op.drop_column('prix_unitaire')


def downgrade() -> None:
    # Le vidage des données n'est pas réversible (pas de sauvegarde du contenu supprimé) —
    # seule la colonne prix_unitaire est restaurée, vide.
    with op.batch_alter_table('pieces_detachees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('prix_unitaire', sa.FLOAT(), nullable=True))
