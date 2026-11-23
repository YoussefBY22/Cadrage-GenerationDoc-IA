"""Machine à états des livrables (06 §8) : fonctions pures, sans accès aux données."""

from dataclasses import dataclass

from app.domain.workflow import State

# (état courant, état demandé) autorisés
ALLOWED: frozenset[tuple[str, str]] = frozenset({
    ("draft", "in_review"),
    ("in_review", "approved"),
    ("in_review", "rejected"),
    ("in_review", "draft"),      # retirer (auteur)
    ("rejected", "draft"),       # reprendre
})


class WorkflowError(Exception):
    """Erreur métier : code stable + statut HTTP (409 sauf rôle insuffisant : 403)."""

    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass(frozen=True)
class TransitionContext:
    current: State
    to: State
    reason: str | None
    actor_id: str
    actor_can_review: bool          # reviewer/admin du dossier
    version_author_id: str          # auteur de la dernière version
    deliverable_author_id: str
    allow_self_approval: bool = False
    unacknowledged_failures: int = 0
    sections_complete: bool = True
    unverified_initiatives: int = 0


def check_transition(ctx: TransitionContext) -> None:
    """Lève WorkflowError si la transition est interdite."""
    if (ctx.current, ctx.to) not in ALLOWED:
        raise WorkflowError("INVALID_TRANSITION",
                            f"Transition impossible : {ctx.current} -> {ctx.to}")
    if ctx.to == "rejected" and not (ctx.reason or "").strip():
        raise WorkflowError("REASON_REQUIRED", "Un motif est obligatoire pour refuser")
    if ctx.current == "in_review" and ctx.to == "draft" and ctx.actor_id not in (
            ctx.deliverable_author_id, ctx.version_author_id):
        raise WorkflowError("AUTHOR_ONLY", "Seul l'auteur peut retirer le livrable de la revue")
    if ctx.to == "approved":
        if not ctx.actor_can_review:
            raise WorkflowError("FORBIDDEN_ROLE", "Rôle relecteur ou admin requis", status=403)
        if ctx.actor_id in (ctx.version_author_id, ctx.deliverable_author_id) \
                and not ctx.allow_self_approval:
            raise WorkflowError("FOUR_EYES", "L'approbateur doit différer de l'auteur")
        if ctx.unverified_initiatives:
            raise WorkflowError(
                "UNVERIFIED_INITIATIVES",
                f"{ctx.unverified_initiatives} problème(s) d'initiatives : constat absent, "
                "inconnu ou non validé, ou feuille de route vide")
        if ctx.unacknowledged_failures:
            raise WorkflowError(
                "UNACKNOWLEDGED_FAILURES",
                f"{ctx.unacknowledged_failures} phrase(s) en échec non acquittée(s)")
        if not ctx.sections_complete:
            raise WorkflowError("INCOMPLETE_SECTIONS",
                                "Toutes les sections doivent être présentes (ou refus acquitté)")


def can_edit(state: State) -> bool:
    """Édition permise en brouillon ; sur un livrable approuvé elle le ramène en brouillon."""
    return state in ("draft", "approved")
