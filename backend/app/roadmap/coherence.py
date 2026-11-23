"""Contrôles de cohérence de la feuille de route (docs/15 §3, contrôles 1 à 8) : pur, sans modèle ni E/S.

Un code par contrôle ; les phrases d'affichage sont de la responsabilité de l'interface.

| Code                          | Contrôle                                                          | Gravité  |
|-------------------------------|-------------------------------------------------------------------|----------|
| FINDING_NO_INITIATIVE         | 1. constat majeur (gravité « high ») sans initiative              | warning  |
| INITIATIVE_UNANCHORED         | 2. initiative sans constat ou sans priorité institutionnelle      | warning  |
| PRIORITY_NO_INITIATIVE        | 3. priorité institutionnelle validée sans initiative              | warning  |
| INITIATIVE_DUPLICATES_PROJECT | 4. initiative en doublon d'un projet non terminé                  | warning  |
| DEPENDENCY_ORDER              | 5. dépendance cyclique, ou initiative placée avant son prérequis  | blocking |
| INHERITED_PRIORITY            | 6. prérequis moins prioritaire que l'initiative qui en dépend     | info     |
| SCORE_TIE                     | 7. égalité de score, départagée par une règle explicite           | info     |
| NO_DURATION                   | 8. durée absente : un ordre, aucune date                          | info     |

Le contrôle 9 (ToR/CdC contredisant l'initiative) relève d'un autre lot.
Seules les priorités au statut « validated » comptent.
"""

from __future__ import annotations

import heapq
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.coeur import ExistingProject, Priority
from app.domain.generation import Finding
from app.domain.roadmap import Initiative, ScoredInitiative

from .graph import analyze

FINDING_NO_INITIATIVE = "FINDING_NO_INITIATIVE"
INITIATIVE_UNANCHORED = "INITIATIVE_UNANCHORED"
PRIORITY_NO_INITIATIVE = "PRIORITY_NO_INITIATIVE"
INITIATIVE_DUPLICATES_PROJECT = "INITIATIVE_DUPLICATES_PROJECT"
DEPENDENCY_ORDER = "DEPENDENCY_ORDER"
INHERITED_PRIORITY = "INHERITED_PRIORITY"
SCORE_TIE = "SCORE_TIE"
NO_DURATION = "NO_DURATION"

CODES = (FINDING_NO_INITIATIVE, INITIATIVE_UNANCHORED, PRIORITY_NO_INITIATIVE,
         INITIATIVE_DUPLICATES_PROJECT, DEPENDENCY_ORDER, INHERITED_PRIORITY, SCORE_TIE,
         NO_DURATION)

Severity = Literal["blocking", "warning", "info"]
_SEVERITY = {DEPENDENCY_ORDER: "blocking", INHERITED_PRIORITY: "info", SCORE_TIE: "info",
             NO_DURATION: "info"}
_FINDING_WEIGHT = {"high": 3, "medium": 2, "low": 1}
# Projets que l'initiative risque de dupliquer : tout sauf « done ».
DUPLICATE_STATES = ("existing", "in_progress", "planned")
DUPLICATE_THRESHOLD = 0.75  # « Recruter des agents de formation » ≠ « Formation agents » (0,67)


class Issue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    severity: Severity
    refs: dict[str, object]  # identifiants concernés + détails (jamais de prose)


class Link(BaseModel):
    """Un maillon de la chaîne, avec les passages qui le fondent (navigables)."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    source_ids: list[str] = []
    kind: str = ""  # gravité (constat), rang (priorité), initiative | project (dépendance)
    extra: dict[str, object] = {}


class Chain(BaseModel):
    """constat → objectif → initiative → priorité → dépendance → source, pour une initiative."""

    model_config = ConfigDict(frozen=True)

    initiative_id: str
    title: str
    objective: str
    expected_result: str
    indicator: str
    proposal_status: str  # proposed (proposition IA) | accepted (un humain l'a acceptée)
    proposal_flags: list[str]  # nombres de la proposition absents des sources
    findings: list[Link]
    priorities: list[Link]
    dependencies: list[Link]
    source_ids: list[str]  # tous les passages de la chaîne, sans doublon
    rank: int
    wave: int
    inherited_rank: int | None
    position: int
    start_week: int | None
    end_week: int | None
    issues: list[str]  # codes des contrôles qui visent cette initiative


class SequenceItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    initiative_id: str
    position: int  # ordre d'exécution : prérequis d'abord, puis vague, puis rang
    start_week: int | None  # semaines relatives, seulement si toutes les durées utiles sont connues
    end_week: int | None


class CoherenceReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    issues: list[Issue]
    chains: list[Chain]
    sequence: list[SequenceItem]

    def codes(self) -> set[str]:
        return {i.code for i in self.issues}


# --- normalisation pour le doublon ---------------------------------------------------------------
_STOP = frozenset(["le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou", "en", "au", "aux", "pour", "par", "sur", "dans", "avec", "sans", "the", "a", "an", "of", "and", "or", "to", "for", "in", "on", "with", "by"])


def _tokens(text: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    out = set()
    for w in re.findall(r"[a-z0-9]+", plain):
        if w in _STOP or len(w) < 3:
            continue
        out.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return out


def similarity(a: str, b: str) -> float:
    """Jaccard des mots significatifs (pas d'inclusion : « Système information » n'est pas un audit)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 3)


# --- départage explicite des égalités ------------------------------------------------------------
TIE_CRITERIA = ("priority_rank", "finding_severity", "dependents", "title")


def tiebreak_keys(initiatives: list[Initiative], findings: list[Finding],
                  priorities: list[Priority]) -> dict[str, tuple]:
    """Clé de départage (ordre croissant = plus prioritaire), jamais l'ordre du modèle.

    1. meilleur rang parmi les priorités validées liées (plus petit d'abord) ;
    2. gravité la plus haute parmi les constats liés (plus grave d'abord) ;
    3. nombre d'initiatives qui en dépendent (plus d'abord) ;
    4. titre (ordre alphabétique) ; 5. identifiant.
    """
    ranks = {p.id: p.rank for p in priorities if p.status == "validated"}
    sev = {f.id: _FINDING_WEIGHT.get(f.severity, 0) for f in findings}
    dependents: dict[str, int] = {}
    for ini in initiatives:
        for d in set(ini.depends_on):
            dependents[d] = dependents.get(d, 0) + 1
    keys = {}
    for ini in initiatives:
        best_rank = min((ranks[p] for p in ini.priority_ids if p in ranks), default=10**9)
        worst = max((sev.get(f, 0) for f in ini.finding_ids), default=0)
        keys[ini.id] = (best_rank, -worst, -dependents.get(ini.id, 0), ini.title.casefold(), ini.id)
    return keys


def _decided_by(keys: list[tuple]) -> str:
    for idx, name in enumerate(TIE_CRITERIA):
        if len({k[idx] for k in keys}) > 1:
            return name
    return "id"


# --- séquence ------------------------------------------------------------------------------------
def build_sequence(items: list[ScoredInitiative],
                   projects: list[ExistingProject] | None = None) -> list[SequenceItem]:
    """Ordre d'exécution (tri topologique, vague puis rang) ; semaines seulement si TOUT est connu.

    Une dépendance vers un projet non terminé rend le début inconnu : ordre seulement.
    """
    pstate = {p.id: p.state for p in projects or []}
    by_id = {x.initiative.id: x for x in items}
    preds = {i: sorted({d for d in x.initiative.depends_on if d in by_id and d != i})
             for i, x in by_id.items()}
    succs: dict[str, list[str]] = {i: [] for i in by_id}
    for i, ps in preds.items():
        for p in ps:
            succs[p].append(i)
    indeg = {i: len(ps) for i, ps in preds.items()}
    key = {i: (x.wave, x.rank, i) for i, x in by_id.items()}
    heap = [(key[i], i) for i, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        _, u = heapq.heappop(heap)
        order.append(u)
        for v in succs[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, (key[v], v))
    placed = set(order)
    order += sorted((i for i in by_id if i not in placed), key=lambda i: key[i])  # cycles
    ends: dict[str, int | None] = {}
    seq = []
    for pos, iid in enumerate(order, 1):
        dur = by_id[iid].initiative.duration_weeks
        deps = preds[iid]
        proj_ok = all(pstate.get(p) == "done" for p in by_id[iid].initiative.depends_on_projects)
        known = (dur is not None and proj_ok
                 and all(d in ends and ends[d] is not None for d in deps))
        start = max((ends[d] for d in deps), default=0) if known else None
        end = start + dur if known and start is not None and dur is not None else None
        ends[iid] = end
        seq.append(SequenceItem(initiative_id=iid, position=pos, start_week=start, end_week=end))
    return seq


def _effective_ranks(items: list[ScoredInitiative]) -> dict[str, int]:
    """Rang hérité : le meilleur rang parmi l'initiative et tout ce qui en dépend (transitif)."""
    eff = {x.initiative.id: x.rank for x in items}
    for _ in range(len(items) + 1):
        changed = False
        for x in items:
            for d in x.initiative.depends_on:
                if d in eff and eff[x.initiative.id] < eff[d]:
                    eff[d] = eff[x.initiative.id]
                    changed = True
        if not changed:
            break
    return eff


# --- les huit contrôles --------------------------------------------------------------------------
def check(items: list[ScoredInitiative], findings: list[Finding], priorities: list[Priority],
          projects: list[ExistingProject]) -> CoherenceReport:
    """Contrôles 1 à 8 + chaînes ; les constats et priorités fournis sont ceux qui font foi."""
    validated = {p.id: p for p in priorities if p.status == "validated"}
    fmap = {f.id: f for f in findings}
    pmap = {p.id: p for p in projects}
    by_id = {x.initiative.id: x for x in items}
    issues: list[Issue] = []

    def add(code: str, **refs) -> None:
        issues.append(Issue(code=code, severity=_SEVERITY.get(code, "warning"), refs=refs))

    # 1. constat majeur sans initiative
    covered = {f for x in items for f in x.initiative.finding_ids}
    for f in findings:
        if f.severity == "high" and f.id not in covered:
            add(FINDING_NO_INITIATIVE, finding_id=f.id)

    # 2. initiative sans constat ou sans priorité institutionnelle
    for x in sorted(items, key=lambda x: x.rank):
        ini = x.initiative
        missing = []
        if not any(f in fmap for f in ini.finding_ids):
            missing.append("finding")
        if not any(p in validated for p in ini.priority_ids):
            missing.append("priority")
        if missing:
            add(INITIATIVE_UNANCHORED, initiative_id=ini.id, missing=missing)

    # 3. priorité validée sans initiative
    used = {p for x in items for p in x.initiative.priority_ids}
    for p in sorted(validated.values(), key=lambda p: (p.rank, p.id)):
        if p.id not in used:
            add(PRIORITY_NO_INITIATIVE, priority_id=p.id)

    # 4. doublon d'un projet non terminé (sauf si l'initiative en dépend explicitement)
    for x in sorted(items, key=lambda x: x.rank):
        ini = x.initiative
        for pj in projects:
            if pj.state not in DUPLICATE_STATES or pj.id in ini.depends_on_projects:
                continue
            sim = similarity(ini.title, pj.title)
            if sim >= DUPLICATE_THRESHOLD:
                add(INITIATIVE_DUPLICATES_PROJECT, initiative_id=ini.id, project_id=pj.id,
                    similarity=sim)

    # 5. cycle, ou initiative placée (vague) avant son prérequis
    _, cycles, _ = analyze([x.initiative.model_copy(update={
        "depends_on": [d for d in x.initiative.depends_on if d in by_id]}) for x in items])
    for cyc in cycles:
        add(DEPENDENCY_ORDER, kind="cycle", initiative_ids=cyc)
    for x in sorted(items, key=lambda x: x.rank):
        for d in sorted(set(x.initiative.depends_on)):
            if d in by_id and by_id[d].wave > x.wave:
                add(DEPENDENCY_ORDER, kind="before_prerequisite",
                    initiative_ids=[x.initiative.id, d])

    # 6. priorité héritée
    eff = _effective_ranks(items)
    for x in sorted(items, key=lambda x: x.rank):
        if eff[x.initiative.id] < x.rank:
            add(INHERITED_PRIORITY, initiative_id=x.initiative.id, rank=x.rank,
                inherited_rank=eff[x.initiative.id])

    # 7. égalité de score : la règle de départage est affichée
    keys = tiebreak_keys([x.initiative for x in items], findings, priorities)
    groups: dict[float, list[ScoredInitiative]] = {}
    for x in items:
        groups.setdefault(x.score, []).append(x)
    for score, grp in sorted(groups.items(), reverse=True):
        if len(grp) > 1:
            grp = sorted(grp, key=lambda x: x.rank)
            add(SCORE_TIE, score=score, initiative_ids=[x.initiative.id for x in grp],
                decided_by=_decided_by([keys[x.initiative.id] for x in grp]))

    # 8. durée absente : ordre seulement
    for x in sorted(items, key=lambda x: x.rank):
        if x.initiative.duration_weeks is None:
            add(NO_DURATION, initiative_id=x.initiative.id)

    sequence = build_sequence(items, projects)
    seq = {s.initiative_id: s for s in sequence}
    by_init: dict[str, list[str]] = {}
    for i in issues:
        targets = [i.refs["initiative_id"]] if "initiative_id" in i.refs else []
        targets += list(i.refs.get("initiative_ids", []))  # type: ignore[call-overload]
        for iid in targets:
            by_init.setdefault(str(iid), []).append(i.code)

    chains = []
    for x in sorted(items, key=lambda x: x.rank):
        ini = x.initiative
        f_links = [Link(id=f, title=fmap[f].text, source_ids=list(fmap[f].source_ids),
                        kind=fmap[f].severity) for f in dict.fromkeys(ini.finding_ids) if f in fmap]
        p_links = [Link(id=p, title=validated[p].title, source_ids=list(validated[p].source_ids),
                        kind=str(validated[p].rank)) for p in dict.fromkeys(ini.priority_ids)
                   if p in validated]
        d_links = [Link(id=d, title=by_id[d].initiative.title, kind="initiative")
                   for d in dict.fromkeys(ini.depends_on) if d in by_id]
        d_links += [Link(id=d, title=pmap[d].title, source_ids=list(pmap[d].source_ids),
                         kind="project", extra={"state": pmap[d].state})
                    for d in dict.fromkeys(ini.depends_on_projects) if d in pmap]
        sources = list(dict.fromkeys(s for ln in (*f_links, *p_links, *d_links)
                                     for s in ln.source_ids))
        chains.append(Chain(
            initiative_id=ini.id, title=ini.title, objective=ini.objective,
            expected_result=ini.expected_result, indicator=ini.indicator,
            proposal_status=ini.proposal_status, proposal_flags=list(ini.proposal_flags),
            findings=f_links,
            priorities=p_links, dependencies=d_links, source_ids=sources, rank=x.rank,
            wave=x.wave, inherited_rank=eff[ini.id] if eff[ini.id] < x.rank else None,
            position=seq[ini.id].position, start_week=seq[ini.id].start_week,
            end_week=seq[ini.id].end_week, issues=list(dict.fromkeys(by_init.get(ini.id, [])))))
    return CoherenceReport(issues=issues, chains=chains, sequence=sequence)
