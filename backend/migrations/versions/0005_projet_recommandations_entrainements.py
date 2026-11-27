"""Fiche projet, recommandations des rapports d'audit, registre des entraînements.

Révision : 0005
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_TABLES = ["dossier_profiles", "report_checks", "audit_recommendations", "training_runs",
           "training_eval_points", "training_task_scores"]


def upgrade() -> None:
    from app.storage.schema import metadata

    metadata.create_all(op.get_bind(), tables=[metadata.tables[t] for t in _TABLES],
                        checkfirst=True)


def downgrade() -> None:
    from app.storage.schema import metadata

    metadata.drop_all(op.get_bind(), tables=[metadata.tables[t] for t in reversed(_TABLES)])
