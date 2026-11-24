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
