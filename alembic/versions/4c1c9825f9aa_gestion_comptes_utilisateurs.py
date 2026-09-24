"""gestion comptes utilisateurs (creation admin, mdp temporaire)

Revision ID: 4c1c9825f9aa
Revises: 85199e3feae7
Create Date: 2026-09-22 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c1c9825f9aa'
down_revision: Union[str, None] = '85199e3feae7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite ne supporte pas ALTER COLUMN direct — batch_alter_table recree la table sous le
    # capot (seul mode compatible ici ; sur Postgres ce serait un ALTER direct classique).
    with op.batch_alter_table('techniciens') as batch_op:
        # Compte cree par un admin/chef avec mot de passe temporaire genere — doit le changer a
        # la premiere connexion. Toujours False pour les comptes existants (deja leur propre mdp).
        batch_op.add_column(
            sa.Column('doit_changer_mdp', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        # specialite/telephone ne sont plus saisis a la creation (formulaire reduit a prenom/nom/
        # role) — pertinents uniquement une fois le compte technicien complete par son titulaire.
        batch_op.alter_column('specialite', existing_type=sa.String(length=255), nullable=True)
        batch_op.alter_column('telephone', existing_type=sa.String(length=50), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('techniciens') as batch_op:
        batch_op.alter_column('telephone', existing_type=sa.String(length=50), nullable=False)
        batch_op.alter_column('specialite', existing_type=sa.String(length=255), nullable=False)
        batch_op.drop_column('doit_changer_mdp')
