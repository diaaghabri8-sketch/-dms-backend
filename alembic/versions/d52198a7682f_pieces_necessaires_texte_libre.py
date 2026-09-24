"""pieces necessaires texte libre

Migration A du chantier "pièces de rechange en texte libre" (voir SUIVI_PROJET.md) —
PieceNecessaire.piece_detachee_id (FK, NOT NULL) devient description_libre (texte libre,
NOT NULL), avec préservation des données : chaque ligne existante récupère le nom de sa pièce
catalogue AVANT que le lien ne soit retiré. Le vidage du catalogue PieceDetachee et le retrait
de son prix (migration B, séparée et postérieure) doivent impérativement s'exécuter APRÈS
celle-ci — sinon le backfill n'aurait plus rien à lire.

Revision ID: d52198a7682f
Revises: 98e1027581c3
Create Date: 2026-08-15 12:52:08.987374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd52198a7682f'
down_revision: Union[str, None] = '98e1027581c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Nouvelle colonne, nullable pour l'instant (le backfill doit pouvoir s'exécuter avant
    #    qu'elle ne devienne obligatoire).
    op.add_column('pieces_necessaires', sa.Column('description_libre', sa.String(length=255), nullable=True))

    # 2. Backfill : copie le nom de la pièce catalogue liée, pour chaque ligne existante —
    #    dernière occasion de le faire, PieceDetachee sera vidée en migration B.
    connection = op.get_bind()
    pieces_necessaires = sa.table(
        'pieces_necessaires',
        sa.column('id', sa.Integer),
        sa.column('piece_detachee_id', sa.Integer),
        sa.column('description_libre', sa.String),
    )
    pieces_detachees = sa.table('pieces_detachees', sa.column('id', sa.Integer), sa.column('nom', sa.String))
    rows = connection.execute(
        sa.select(pieces_necessaires.c.id, pieces_detachees.c.nom)
        .select_from(pieces_necessaires)
        .join(pieces_detachees, pieces_detachees.c.id == pieces_necessaires.c.piece_detachee_id)
    ).fetchall()
    for row in rows:
        connection.execute(
            pieces_necessaires.update()
            .where(pieces_necessaires.c.id == row.id)
            .values(description_libre=row.nom)
        )
    # Filet de sécurité : une ligne dont la pièce catalogue liée aurait déjà été supprimée
    # avant cette migration (orpheline) n'aurait rien reçu du backfill ci-dessus — éviter un
    # NOT NULL constraint violation à l'étape 3 plutôt qu'une perte silencieuse d'historique.
    connection.execute(
        pieces_necessaires.update()
        .where(pieces_necessaires.c.description_libre.is_(None))
        .values(description_libre='Pièce non tracée (catalogue supprimé)')
    )

    # 3. Colonne obligatoire + retrait du lien catalogue — nécessite batch_alter_table sur
    #    SQLite (DROP COLUMN sur une colonne avec clé étrangère, déjà rencontré plusieurs fois
    #    sur ce projet).
    with op.batch_alter_table('pieces_necessaires', schema=None) as batch_op:
        batch_op.alter_column('description_libre', existing_type=sa.String(length=255), nullable=False)
        batch_op.drop_column('piece_detachee_id')


def downgrade() -> None:
    with op.batch_alter_table('pieces_necessaires', schema=None) as batch_op:
        batch_op.add_column(sa.Column('piece_detachee_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(
            'fk_pieces_necessaires_piece_detachee_id', 'pieces_detachees', ['piece_detachee_id'], ['id']
        )
        batch_op.drop_column('description_libre')
