"""Feuille de route par AXES : outils sans modèle (doublons, lots qui tiennent, noms d'axes).

Pourquoi : un vrai rapport donne 50 à 100 constats ; tout envoyer en une question dépasse la fenêtre du modèle
(4 096 jetons sur un GPU de 4 Go). On procède donc comme un cabinet de conseil : les constats sont rangés en
axes (gouvernance, processus…), puis les initiatives sont proposées axe par axe, chaque appel restant petit.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Sequence

from app.domain.generation import Finding

UNCLASSIFIED = "Autres constats"
_STOP = {"de", "des", "du", "la", "le", "les", "l", "d", "et", "en", "a", "au", "aux", "un", "une", "pour",
         "par", "sur", "dans", "ne", "pas", "que", "qui", "the", "of", "and", "to", "in", "is", "not"}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def axis_key(name: str) -> str:
    """Clé de comparaison d'un nom d'axe : casse, accents, ponctuation et « axe » initial ignorés."""
    k = _fold(name)
    return re.sub(r"^axe\s+", "", k)


def _words(text: str) -> set[str]:
    return {w for w in _fold(text).split() if w not in _STOP and len(w) > 1}


def dedupe(findings: Sequence[Finding], threshold: float = 0.85) -> tuple[list[Finding], dict[str, list[str]]]:
    """Garde un représentant par groupe de constats quasi identiques (mots communs / mots ≥ seuil).

    Renvoie (représentants, {id du représentant: [ids des doublons]}). Aucun constat n'est perdu : les doublons
    suivent leur représentant (même axe, mêmes initiatives).
    """
    reps: list[tuple[Finding, set[str]]] = []
    dups: dict[str, list[str]] = {}
    for f in findings:
        w = _words(f.text)
        hit = None
        for r, rw in reps:
            if w and rw and len(w & rw) / max(len(w), len(rw)) >= threshold:
                hit = r
                break
        if hit is None:
            reps.append((f, w))
            dups[f.id] = []
        else:
            dups[hit.id].append(f.id)
    return [r for r, _ in reps], dups


def batches[T](items: Sequence[T], cost: Callable[[T], int], budget: int) -> list[list[T]]:
    """Lots consécutifs dont le coût total tient dans `budget` ; un élément trop gros forme un lot seul."""
    out: list[list[T]] = []
    cur: list[T] = []
    used = 0
    for it in items:
        c = cost(it)
        if cur and used + c > budget:
            out.append(cur)
            cur, used = [], 0
        cur.append(it)
        used += c
    if cur:
        out.append(cur)
    return out


class AxisBook:
    """Axes créés au fil des lots : un même nom (à la casse et aux accents près) = un même axe."""

    def __init__(self) -> None:
        self.names: list[str] = []
        self._by_key: dict[str, str] = {}
        self.of: dict[str, str] = {}  # id du constat -> nom d'axe

    def add(self, name: str) -> str:
        key = axis_key(name)
        if not key:
            return UNCLASSIFIED
        if key not in self._by_key:
            clean = re.sub(r"\s+", " ", name).strip()
            clean = re.sub(r"^axe\b\s*:?\s*", "", clean, flags=re.IGNORECASE) or clean
            self._by_key[key] = clean[:1].upper() + clean[1:]
            self.names.append(self._by_key[key])
        return self._by_key[key]

    def assign(self, finding_id: str, name: str) -> None:
        if finding_id not in self.of:  # le premier axe donné l'emporte
            self.of[finding_id] = self.add(name)

    def groups(self, findings: Sequence[Finding]) -> list[tuple[str, list[Finding]]]:
        """Axes dans l'ordre de création, puis « Autres constats » pour ce que le modèle n'a pas rangé."""
        out: dict[str, list[Finding]] = {}
        for f in findings:
            out.setdefault(self.of.get(f.id, UNCLASSIFIED), []).append(f)
        order = [n for n in self.names if n in out] + ([UNCLASSIFIED] if UNCLASSIFIED in out else [])
        return [(n, out[n]) for n in order]


def majority_theme(findings: Sequence[Finding]) -> str | None:
    """Axe d'une initiative quand on n'a pas eu besoin de découper : thème d'extraction le plus fréquent."""
    themes = Counter(f.theme.strip() for f in findings if f.theme and f.theme.strip())
    return themes.most_common(1)[0][0] if themes else None


# --- regroupement par le sens (vecteurs) : fiable même avec un petit modèle -----------------------------------
MAX_AXES = 6


def parse_axes(text: str) -> list[str]:
    """Axes imposés par le consultant : un par ligne ou séparés par « ; » (doublons et vides retirés, 7 au plus)."""
    out: list[str] = []
    for part in re.split(r"[;\n]", text or ""):
        name = re.sub(r"^[\s\-•*\d.)]+", "", part).strip()
        if name and axis_key(name) not in {axis_key(x) for x in out}:
            out.append(name[:120])
    return out[:7]


def _cos(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return num / (na * nb) if na and nb else 0.0


def nearest(vectors: Sequence[Sequence[float]], targets: Sequence[Sequence[float]]) -> list[int]:
    """Indice de la cible la plus proche (cosinus) pour chaque vecteur."""
    return [max(range(len(targets)), key=lambda j, v=v: _cos(v, targets[j])) for v in vectors]


def k_for(n: int) -> int:
    """Nombre d'axes visé : 2 à 6 selon le nombre de constats (55 constats -> 5 axes)."""
    return max(2, min(MAX_AXES, round((n / 2) ** 0.5))) if n >= 4 else 1


def cluster(vectors: Sequence[Sequence[float]], k: int) -> list[list[int]]:
    """Regroupement hiérarchique (liaison moyenne, cosinus) jusqu'à k groupes ; déterministe."""
    groups = [[i] for i in range(len(vectors))]
    sim = [[_cos(a, b) for b in vectors] for a in vectors]

    def link(g: list[int], h: list[int]) -> float:
        return sum(sim[i][j] for i in g for j in h) / (len(g) * len(h))

    while len(groups) > max(1, k):
        best, pair = -2.0, (0, 1)
        for x in range(len(groups)):
            for y in range(x + 1, len(groups)):
                s_ = link(groups[x], groups[y])
                if s_ > best:
                    best, pair = s_, (x, y)
        x, y = pair
        groups[x] = sorted(groups[x] + groups[y])
        del groups[y]
    return sorted(groups, key=lambda g: (-len(g), g[0]))


def central(vectors: Sequence[Sequence[float]], members: list[int], limit: int) -> list[int]:
    """Les membres les plus représentatifs du groupe (proches de tous les autres), pour le nommer."""
    def score(i: int) -> float:
        return sum(_cos(vectors[i], vectors[j]) for j in members)
    return sorted(members, key=lambda i: -score(i))[:limit]
