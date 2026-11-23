"""Décisions humaines (FR-23) : saisie, confirmation, édition. Rien n'est jamais confirmé par le modèle."""

from app.domain.decisions import Decision
from app.domain.workflow import CurrentUser

from .generation import GenerationError


def create(repo, dossier_id: str, user: CurrentUser, *, category: str, text: str,
           status: str = "proposed") -> Decision:
    text = text.strip()
    if not text:
        raise GenerationError(422, "EMPTY_DECISION", "Le texte de la décision est vide")
    d = repo.create_decision(dossier_id, category=category, text=text, status=status,
                             author_id=user.id)
    repo.audit(user.id, "decision.create", "decision", d.id,
               {"category": category, "status": status})
    return d


def patch(repo, d: Decision, user: CurrentUser, changes: dict) -> Decision:
    """Texte ou catégorie modifiés : la confirmation tombe, la décision est à reconfirmer."""
    values = {k: (v.strip() if isinstance(v, str) else v) for k, v in changes.items()
              if k in ("category", "text") and v is not None}
    if "text" in values and not values["text"]:
        raise GenerationError(422, "EMPTY_DECISION", "Le texte de la décision est vide")
    if any(values.get(k, getattr(d, k)) != getattr(d, k) for k in values) and d.status == "confirmed":
        values.update(status="proposed", confirmed_by=None, confirmed_at=None)
    updated = repo.update_decision(d.id, **values)
    repo.audit(user.id, "decision.update", "decision", d.id,
               {k: v for k, v in values.items() if k not in ("confirmed_at",)})
    return updated


def confirm(repo, d: Decision, user: CurrentUser) -> Decision:
    from app.storage.schema import utcnow

    updated = repo.update_decision(d.id, status="confirmed", confirmed_by=user.id,
                                   confirmed_at=utcnow(), author_id=d.author_id or user.id)
    repo.audit(user.id, "decision.confirm", "decision", d.id, {"category": d.category})
    return updated


def retract(repo, d: Decision, user: CurrentUser) -> Decision:
    updated = repo.update_decision(d.id, status="proposed", confirmed_by=None, confirmed_at=None)
    repo.audit(user.id, "decision.retract", "decision", d.id, {})
    return updated
