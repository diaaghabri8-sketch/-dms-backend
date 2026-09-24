"""appels_offres (veille marches publics)

Revision ID: c9b82357e1ce
Revises: 4c1c9825f9aa
Create Date: 2026-09-23 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9b82357e1ce'
down_revision: Union[str, None] = '4c1c9825f9aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'appels_offres',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('id_externe', sa.String(length=50), nullable=False),
        sa.Column('titre', sa.String(length=1000), nullable=False),
        sa.Column('organisme_acheteur', sa.String(length=500), nullable=False),
        sa.Column('date_publication', sa.DateTime(), nullable=True),
        sa.Column('date_limite_offres', sa.DateTime(), nullable=True),
        sa.Column('lien_avis', sa.String(length=500), nullable=False),
        sa.Column('lien_pdf', sa.String(length=1000), nullable=True),
        sa.Column('mot_cle_trouve', sa.String(length=255), nullable=False),
        sa.Column('statut', sa.String(length=20), nullable=False, server_default='nouveau'),
        sa.Column('date_detection', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_appels_offres_id_externe', 'appels_offres', ['id_externe'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_appels_offres_id_externe', table_name='appels_offres')
    op.drop_table('appels_offres')
