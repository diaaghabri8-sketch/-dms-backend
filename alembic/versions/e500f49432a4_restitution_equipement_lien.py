"""restitution equipement lien

Revision ID: e500f49432a4
Revises: 873b0b77d5dd
Create Date: 2026-08-18 00:10:16.364768

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e500f49432a4'
down_revision: Union[str, None] = '873b0b77d5dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TypeDocument.BON_RESTITUTION est une valeur d'enum Python supplémentaire — vraie sur
    # SQLite (colonne VARCHAR sans contrainte CHECK, aucune migration nécessaire là), mais
    # FAUX sur Postgres où `type_document` est un vrai type ENUM natif : corrigé rétroactivement
    # le 2026-09-24 directement dans la migration d'origine (f083e97f6e53) plutôt qu'ici, pour
    # éviter un `ALTER TYPE ... ADD VALUE` utilisé dans la même transaction que celle qui
    # l'ajoute (impossible sur Postgres, voir 9c7da91b27c3 et SUIVI_PROJET.md).
    with op.batch_alter_table('equipements_attente_reparation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('restitution_intervention_id', sa.String(length=20), nullable=True))
        batch_op.create_foreign_key(
            'fk_equipements_attente_reparation_restitution_intervention_id',
            'interventions', ['restitution_intervention_id'], ['id'], ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('equipements_attente_reparation', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_equipements_attente_reparation_restitution_intervention_id', type_='foreignkey'
        )
        batch_op.drop_column('restitution_intervention_id')
