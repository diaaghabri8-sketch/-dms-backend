"""type_intervention snake_case values

Revision ID: b9361b4e91f8
Revises: 320d855d5ad4
Create Date: 2026-08-07 21:15:37.362860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9361b4e91f8'
down_revision: Union[str, None] = '320d855d5ad4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_TO_NEW = {
    "Curatif": "curatif",
    "Préventif": "preventif",
    "Installation": "installation",
    "Formation": "formation",
}
_NEW_TO_OLD = {v: k for k, v in _OLD_TO_NEW.items()}


def upgrade() -> None:
    # TypeIntervention passe de valeurs "Curatif"/"Préventif" (majuscule+accent) à un
    # snake_case minuscule cohérent avec les autres enums du projet. Colonne stockée en
    # VARCHAR côté SQLite (pas de vrai type ENUM), donc uniquement une migration de données.
    #
    # Sur Postgres : sans objet (no-op) — la migration initiale (9c7da91b27c3) a été corrigée
    # rétroactivement pour créer directement `type_intervention` avec les valeurs snake_case
    # finales, donc aucune ligne "Curatif" n'existe jamais sur une base Postgres neuve. Exécuter
    # cet UPDATE quand même échouerait : les littéraux 'Curatif' n'existent plus dans le type
    # ENUM corrigé (`invalid input value for enum`). Voir SUIVI_PROJET.md.
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        return
    for old, new in _OLD_TO_NEW.items():
        conn.execute(sa.text("UPDATE interventions SET type = :new WHERE type = :old"), {"new": new, "old": old})
        conn.execute(
            sa.text("UPDATE plannings SET type_intervention = :new WHERE type_intervention = :old"),
            {"new": new, "old": old},
        )


def downgrade() -> None:
    # Symétrique de upgrade() : sans objet sur Postgres, 'Curatif' n'existe plus dans le type
    # ENUM corrigé (voir note dans upgrade() et 9c7da91b27c3).
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        return
    for new, old in _NEW_TO_OLD.items():
        conn.execute(sa.text("UPDATE interventions SET type = :old WHERE type = :new"), {"new": new, "old": old})
        conn.execute(
            sa.text("UPDATE plannings SET type_intervention = :old WHERE type_intervention = :new"),
            {"new": new, "old": old},
        )
