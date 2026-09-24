"""equipements multiples par intervention

Revision ID: 1ed9d106e567
Revises: 3b1ac7a49f8f
Create Date: 2026-08-10 18:39:44.406612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ed9d106e567'
down_revision: Union[str, None] = '3b1ac7a49f8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Nouvelle table d'association (many-to-many intervention <-> équipement(s)).
    op.create_table('intervention_equipements',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('intervention_id', sa.String(length=20), nullable=False),
    sa.Column('equipement_id', sa.String(length=20), nullable=True),
    sa.Column('equipement_vente_id', sa.Integer(), nullable=True),
    sa.Column('description_libre', sa.String(length=255), nullable=True),
    sa.Column('sn_saisi_technicien', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['equipement_id'], ['equipements.id'], ),
    sa.ForeignKeyConstraint(['equipement_vente_id'], ['equipements_neuf_a_vendre.id'], ),
    sa.ForeignKeyConstraint(['intervention_id'], ['interventions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    # 2. Migration des données existantes AVANT de supprimer interventions.equipement_id —
    # chaque intervention actuelle avait exactement un équipement (ancien modèle 1-vers-1) :
    # on lui crée la ligne d'association correspondante pour ne rien perdre.
    connection = op.get_bind()
    interventions_table = sa.table(
        'interventions',
        sa.column('id', sa.String),
        sa.column('equipement_id', sa.String),
    )
    intervention_equipements_table = sa.table(
        'intervention_equipements',
        sa.column('intervention_id', sa.String),
        sa.column('equipement_id', sa.String),
    )
    existing = connection.execute(sa.select(interventions_table.c.id, interventions_table.c.equipement_id)).fetchall()
    if existing:
        connection.execute(
            intervention_equipements_table.insert(),
            [{'intervention_id': row.id, 'equipement_id': row.equipement_id} for row in existing],
        )

    # 3. `batch_alter_table` obligatoire ici : SQLite ne supporte pas DROP CONSTRAINT / DROP
    # COLUMN sur une colonne avec clé étrangère sans recréer la table — Alembic s'en charge
    # automatiquement en mode batch (copie -> nouvelle table -> bascule).
    with op.batch_alter_table('interventions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nom_contact', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('nom_etablissement', sa.String(length=255), nullable=True))
        batch_op.drop_column('equipement_id')

    # Ajout d'une contrainte de clé étrangère (pas juste une colonne) : nécessite aussi le
    # mode batch sur SQLite (cf. commentaire ci-dessus).
    with op.batch_alter_table('pieces_necessaires', schema=None) as batch_op:
        batch_op.add_column(sa.Column('intervention_equipement_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_pieces_necessaires_intervention_equipement_id',
            'intervention_equipements', ['intervention_equipement_id'], ['id'], ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('pieces_necessaires', schema=None) as batch_op:
        batch_op.drop_constraint('fk_pieces_necessaires_intervention_equipement_id', type_='foreignkey')
        batch_op.drop_column('intervention_equipement_id')

    with op.batch_alter_table('interventions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('equipement_id', sa.VARCHAR(length=20), nullable=True))
        batch_op.create_foreign_key('fk_interventions_equipement_id', 'equipements', ['equipement_id'], ['id'])
        batch_op.drop_column('nom_etablissement')
        batch_op.drop_column('nom_contact')

    op.drop_table('intervention_equipements')
