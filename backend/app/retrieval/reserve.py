"""Places réservées aux diagnostics dans une liste de passages classés (docs/15 §5) : pur.

Un diagnostic pertinent (présent dans le classement élargi) est remonté jusqu'à `reserved` places ;
il prend la place des passages les plus mal classés qui n'en sont pas. Les autres documents ne sont
jamais masqués : au plus `reserved` places leur sont retirées, au bas du classement.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from app.domain.retrieval import Passage


def reserved_places(k: int) -> int:
    """Un tiers de la liste, au moins une place."""
    return max(1, k // 3)


def reserve_diagnostic_places(ranked: Sequence[Passage], k: int, diagnostic_docs: Collection[str],
                              reserved: int | None = None) -> list[Passage]:
    """`ranked` : classement élargi (par ex. 2 k passages) ; renvoie k passages, étiquettes P1..Pk."""
    reserved = reserved_places(k) if reserved is None else reserved
    diag = set(diagnostic_docs)
    head = list(ranked[:k])
    have = sum(p.chunk.document_id in diag for p in head)
    promote = [p for p in ranked[k:] if p.chunk.document_id in diag][:max(0, reserved - have)]
    for p in promote:
        victims = [q for q in head if q.chunk.document_id not in diag]
        if not victims:
            break
        head.remove(victims[-1])  # le moins bien classé des passages non diagnostic
        head.append(p)
    order = {id(p): i for i, p in enumerate(ranked)}
    head.sort(key=lambda p: order[id(p)])
    return [p.model_copy(update={"label": f"P{i}"}) for i, p in enumerate(head, 1)]
