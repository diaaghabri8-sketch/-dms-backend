"""enable row level security on public tables

Supabase signale "Table publicly accessible / rls_disabled_in_public" sur toutes les tables du
schéma public : par défaut, Supabase expose une API REST publique (PostgREST) sur ce schéma,
interrogeable avec les rôles `anon`/`authenticated` tant que RLS n'est pas activé. Notre backend
ne passe jamais par cette API (connexion directe à Postgres via `DATABASE_URL`, voir
SUIVI_PROJET.md), mais tant que RLS reste désactivé, n'importe qui connaissant l'URL Supabase du
projet peut lire/écrire ces tables directement via PostgREST — le risque est réel même si notre
propre code ne l'emprunte jamais.

Active RLS sur CHAQUE table du schéma public, SANS créer aucune policy : avec RLS activé et
aucune policy permissive, PostgREST (rôles `anon`/`authenticated`, qui ne contournent jamais RLS)
ne voit plus aucune ligne et ne peut plus rien écrire — l'API publique est neutralisée. Le rôle
utilisé par notre backend (`postgres`, propriétaire de chaque table créée par ces migrations) est
lui totalement épargné : un propriétaire de table contourne RLS par défaut (tant que
`FORCE ROW LEVEL SECURITY` n'est pas posé séparément, ce que cette migration ne fait PAS), et ce
même rôle possède en plus l'attribut `BYPASSRLS` sur ce projet Supabase — vérifié avant d'écrire
cette migration par une requête directe (`SELECT rolbypassrls FROM pg_roles WHERE rolname =
current_user` → `true`, et `SELECT tablename, tableowner FROM pg_tables WHERE schemaname =
'public'` → chaque table appartient à `postgres`, voir SUIVI_PROJET.md pour le détail complet).
Double garantie donc que ce correctif est invisible pour le backend.

Liste des tables obtenue dynamiquement à l'exécution (`pg_tables`), jamais codée en dur ici —
pour ne jamais en oublier une au fil des futures migrations qui ajouteront des tables. Inclut
`alembic_version` : elle vit dans le même schéma public, donc dans le même périmètre exposé par
PostgREST, et `postgres` la possède/la contourne exactement comme les autres — aucune raison
technique de l'exclure (ajuster `EXCLUDED_TABLES` ci-dessous si une raison apparaissait plus
tard). Sans effet sur SQLite (pas de concept RLS) : migration no-op sur ce dialecte, pour ne pas
casser le développement local.

Revision ID: d145f17b88a1
Revises: c9b82357e1ce
Create Date: 2026-09-30 19:15:09.601490

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd145f17b88a1'
down_revision: Union[str, None] = 'c9b82357e1ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Aucune table exclue à ce jour (voir docstring ci-dessus) — laissé en place comme point
# d'extension si une future table du schéma public ne devait délibérément pas avoir RLS.
EXCLUDED_TABLES: set[str] = set()


def _public_tables(conn) -> list[str]:
    rows = conn.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    return [row[0] for row in rows if row[0] not in EXCLUDED_TABLES]


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    for table in _public_tables(conn):
        # Identifiant entre guillemets doubles échappés — noms de tables issus de `pg_tables`
        # (catalogue système, jamais une entrée utilisateur), mais on quote proprement par
        # principe plutôt que de supposer qu'aucun nom ne contiendra jamais de caractère spécial.
        quoted = table.replace('"', '""')
        conn.execute(sa.text(f'ALTER TABLE public."{quoted}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    for table in _public_tables(conn):
        quoted = table.replace('"', '""')
        conn.execute(sa.text(f'ALTER TABLE public."{quoted}" DISABLE ROW LEVEL SECURITY'))
