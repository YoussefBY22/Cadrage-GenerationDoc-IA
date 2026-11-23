"""Cœur métier : rôle des documents, priorités institutionnelles, projets existants.

Révision : 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_TABLES = ["priorities", "existing_projects"]


def upgrade() -> None:
    from app.storage.schema import metadata

    bind = op.get_bind()
    # 0001 crée `documents` depuis la métadonnée courante : la colonne peut déjà exister
    # (base neuve) ou manquer (base antérieure à 0003).
    if "role" not in {c["name"] for c in sa.inspect(bind).get_columns("documents")}:
        with op.batch_alter_table("documents") as batch:
            batch.add_column(sa.Column("role", sa.String(16), nullable=False,
                                       server_default="other"))
    metadata.create_all(bind, tables=[metadata.tables[t] for t in _TABLES])


def downgrade() -> None:
    from app.storage.schema import metadata

    bind = op.get_bind()
    metadata.drop_all(bind, tables=[metadata.tables[t] for t in reversed(_TABLES)])
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("role")
