"""Constats (citation, nature, fusion) et recommandations complètes (sous-points, échéance, paragraphes).

Révision : 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_FINDINGS = [("quote", sa.Text()), ("kind", sa.String(12)), ("status", sa.String(12)),
             ("discard_reason", sa.String(200)), ("merged_into", sa.String(32)), ("rewritten", sa.Boolean())]
_RECS = [("intro", sa.Text()), ("sub_points", sa.JSON()), ("deadline", sa.String(200)), ("points", sa.JSON()),
         ("quote", sa.Text())]


def _have(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # 0005 crée audit_recommendations depuis le schéma courant : ses colonnes peuvent déjà exister
    for table, cols in (("findings", _FINDINGS), ("audit_recommendations", _RECS)):
        have = _have(table)
        for name, type_ in cols:
            if name not in have:
                op.add_column(table, sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for table, cols in (("audit_recommendations", _RECS), ("findings", _FINDINGS)):
        have = _have(table)
        for name, _ in reversed(cols):
            if name in have:
                op.drop_column(table, name)
