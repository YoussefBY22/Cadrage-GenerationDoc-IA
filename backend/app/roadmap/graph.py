"""Graphe de dépendances : ordre topologique, cycles, chemin critique (FR-10)."""

import heapq

from app.domain.roadmap import Initiative


def _build(initiatives: list[Initiative]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    ids = {i.id for i in initiatives}
    preds: dict[str, list[str]] = {}
    succs: dict[str, list[str]] = {i: [] for i in sorted(ids)}
    for ini in initiatives:
        for d in ini.depends_on:
            if d not in ids:
                raise ValueError(f"Initiative {ini.id} : dépendance vers un id inconnu « {d} »")
        preds[ini.id] = sorted(set(ini.depends_on))
        for d in preds[ini.id]:
            succs[d].append(ini.id)
    for s in succs.values():
        s.sort()
    return preds, succs


def _kahn(preds: dict[str, list[str]], succs: dict[str, list[str]]) -> list[str]:
    indeg = {k: len(v) for k, v in preds.items()}
    heap = [k for k, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        u = heapq.heappop(heap)
        order.append(u)
        for v in succs[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, v)
    return order


def _dfs(succs, start, u, path, on_path, found) -> None:
    for v in succs[u]:
        if v == start:
            found.append(list(path))
        elif v > start and v not in on_path:
            path.append(v)
            on_path.add(v)
            _dfs(succs, start, v, path, on_path, found)
            on_path.discard(path.pop())


def _cycles(succs: dict[str, list[str]]) -> list[list[str]]:
    """Cycles élémentaires (arête prérequis → dépendant), commençant par le plus petit id."""
    found: list[list[str]] = []
    for start in sorted(succs):
        _dfs(succs, start, start, [start], {start}, found)
    return sorted(found)


def analyze(initiatives: list[Initiative]) -> tuple[list[str], list[list[str]], list[str]]:
    """Renvoie (ordre topologique, cycles, chemin critique).

    Avec cycle : l'ordre ne contient que les nœuds ordonnables et le chemin critique est vide.
    """
    preds, succs = _build(initiatives)
    order = _kahn(preds, succs)
    cycles = _cycles(succs)
    if cycles or not order:
        return order, cycles, []
    if any(i.duration_weeks is None for i in initiatives):
        return order, cycles, []  # sans durées complètes : un ordre, pas de chemin critique inventé
    dur = {i.id: i.duration_weeks for i in initiatives}
    best: dict[str, int] = {}
    prev: dict[str, str | None] = {}
    for u in order:
        bp = None
        for p in preds[u]:  # triés : le plus petit id gagne les égalités
            if bp is None or best[p] > best[bp]:
                bp = p
        best[u] = dur[u] + (best[bp] if bp is not None else 0)
        prev[u] = bp
    end = min(order, key=lambda k: (-best[k], k))
    path = []
    cur: str | None = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return order, cycles, path[::-1]
