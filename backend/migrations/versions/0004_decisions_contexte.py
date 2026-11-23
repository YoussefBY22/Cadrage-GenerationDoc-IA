"""Décisions humaines et fiche de contexte (lot B).

Révision : 0004
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_TABLES = ["decisions", "context_sheets"]


def upgrade() -> None:
    from app.storage.schema import metadata

    metadata.create_all(op.get_bind(), tables=[metadata.tables[t] for t in _TABLES],
                        checkfirst=True)


def downgrade() -> None:
    from app.storage.schema import metadata

    metadata.drop_all(op.get_bind(), tables=[metadata.tables[t] for t in reversed(_TABLES)])
