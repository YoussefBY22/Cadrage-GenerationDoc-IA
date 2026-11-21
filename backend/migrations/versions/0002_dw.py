"""Entrepôt de données : schéma dw (tables en étoile) et vues pour Power BI.

Révision : 0002
"""

from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.dw.schema import SCHEMA, dw_metadata
    from app.dw.views_sql import create_views

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        target = bind
    else:  # SQLite : mêmes tables, sans préfixe de schéma
        target = bind.execution_options(schema_translate_map={SCHEMA: None})
    dw_metadata.create_all(target)
    create_views(bind)


def downgrade() -> None:
    from app.dw.schema import SCHEMA, dw_metadata
    from app.dw.views_sql import drop_views

    bind = op.get_bind()
    drop_views(bind)
    target = bind if bind.dialect.name == "postgresql" else bind.execution_options(
        schema_translate_map={SCHEMA: None})
    dw_metadata.drop_all(target)
    if bind.dialect.name == "postgresql":
        bind.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
