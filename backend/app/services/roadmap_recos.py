"""Feuille de route construite à partir des recommandations du rapport (sans modèle de langage).

Comme le ferait un consultant : chaque recommandation devient un **axe**, chacun de ses sous-points a), b)…
une **initiative** (la recommandation entière s'il n'y en a pas). Les constats liés (paragraphes cités par
le rapport) justifient l'initiative ; chacun va au sous-point dont il est le plus proche par le sens.
La **vague** vient de l'échéance écrite dans le rapport ; à défaut, de la gravité des constats liés.
Chaque choix est écrit en clair (`wave_reason`) : rien n'est placé sans raison lisible.
"""

from __future__ import annotations

import re
from datetime import date

from ..domain.ids import new_id
from ..domain.roadmap import CriterionScore, Initiative

_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
       "novembre", "décembre"]
_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
       "november", "december"]
MOIS = {m: i for i, m in enumerate(_FR, 1)} | {m: i for i, m in enumerate(_EN, 1)} | {"fevrier": 2, "aout": 8,
                                                                                       "decembre": 12}
HORIZONS = {1: "0 à 6 mois", 2: "6 à 12 mois", 3: "12 à 24 mois"}
SEV = {"high": 3, "medium": 2, "low": 1}
SEV_FR = {3: "élevée", 2: "moyenne", 1: "faible"}
ATTACH_MIN = 0.55  # sens minimal pour rattacher un constat sans recommandation à une initiative


def parse_deadline(text: str | None) -> date | None:
    """« D'ici à décembre 2023 » → 2023-12-31 ; « fin 2024 » / « 2025 » → 31 décembre ; sinon None."""
    if not text:
        return None
    low = text.lower()
    year = re.search(r"\b(20\d{2})\b", low)
    if not year:
        return None
    y = int(year.group(1))
    month = next((n for m, n in MOIS.items() if re.search(rf"\b{m}\b", low)), 12)
    if month == 12:
        return date(y, 12, 31)
    return date.fromordinal(date(y, month + 1, 1).toordinal() - 1)


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def wave_for(deadline: str | None, severity: int, today: date) -> tuple[int, str]:
    d = parse_deadline(deadline)
    if d:
        left = months_between(today, d)
        if left < 0:
            # tout ce qui est en retard ne peut pas être en vague 1 : la gravité départage
            wave = {3: 1, 2: 2, 1: 3}.get(severity, 1)
            how = (f"la gravité la plus forte des constats liés ({SEV_FR[severity]})" if severity
                   else "l'absence de constat lié pour départager")
            return wave, (f"Échéance fixée par le rapport : « {deadline} », dépassée de {-left} mois : "
                          f"en retard. L'ordre est fixé par {how} → vague {wave} ({HORIZONS[wave]}).")
        wave = 1 if left <= 6 else 2 if left <= 12 else 3
        return wave, (f"Échéance fixée par le rapport : « {deadline} », dans {left} mois : "
                      f"vague {wave} ({HORIZONS[wave]}).")
    if severity:
        wave = {3: 1, 2: 2, 1: 3}[severity]
        return wave, (f"Pas d'échéance dans le rapport : vague fixée par la gravité la plus forte des constats "
                      f"liés ({SEV_FR[severity]}) → vague {wave} ({HORIZONS[wave]}).")
    return 3, "Pas d'échéance dans le rapport ni de constat lié : placée en dernière vague, à arbitrer."


def to_infinitive(text: str) -> str:
    """« analysant périodiquement… » → « Analyser périodiquement… » (sous-points au participe présent) ;
    « La Commission devrait rendre compte… » → « Rendre compte… » (recommandation sans sous-point)."""
    t = text.strip().rstrip(";.,")
    t = t.split(". ")[0]  # la première phrase porte l'action
    t = re.sub(r"(?i)^(?:la|le|les|l['’])\s*[\w\s'’-]{2,60}?\s+(?:devrait|devraient|doit|doivent)\s+(?:continuer\s+à\s+)?",
               "", t)
    m = re.match(r"^(\w+)ant\b", t)
    if m and len(m.group(1)) > 2:
        stem = m.group(1)
        verb = stem[:-3] + "ir" if stem.endswith("iss") else stem + "er"
        t = verb.replace("geer", "ger") + t[m.end():]
    return t[:1].upper() + t[1:]


def short_title(text: str, limit: int = 140) -> str:
    t = to_infinitive(text)
    if len(t) <= limit:
        return t
    cut = t[:limit]
    for sep in (" (", ", ", " ; ", " afin ", " notamment "):
        k = cut.rfind(sep)
        if k > 50:
            return cut[:k].rstrip(" ,;") + "…"
    return cut.rstrip() + "…"


def _cos(a, b) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


def build(recs: list[dict], findings: list, links: dict, provider, today: date | None = None
          ) -> tuple[list[Initiative], list[str], dict]:
    """recs : recommandations actives (avec sous-points, échéance) ; findings : constats validés actifs ;
    links : constat → {recommendation_ids}. Rend (initiatives, avertissements, statistiques)."""
    today = today or date.today()
    fmap = {f.id: f for f in findings}
    plan = []  # (reco, label, texte)
    for r in sorted(recs, key=lambda r: (r.get("number") or 99, r["title"])):
        subs = r.get("sub_points") or []
        if subs:
            plan += [(r, sp["label"], sp["text"]) for sp in subs]
        else:
            plan.append((r, None, r.get("intro") or r["title"]))
    if not plan:
        return [], [], {}

    by_reco = {r["id"]: [f for f in findings if r["id"] in links.get(f.id, {}).get("recommendation_ids", [])]
               for r in recs}
    vec_plan = provider.embed([f"{r['title']}. {txt}" for r, _, txt in plan])
    vec_f = dict(zip([f.id for f in findings], provider.embed([f.text for f in findings]), strict=True)) \
        if findings else {}
    assigned: dict[int, list[str]] = {i: [] for i in range(len(plan))}
    for r in recs:
        idx = [i for i, (pr, _, _) in enumerate(plan) if pr["id"] == r["id"]]
        for f in by_reco[r["id"]]:
            best = max(idx, key=lambda i: _cos(vec_f[f.id], vec_plan[i]))
            assigned[best].append(f.id)
    linked = {fid for ids in assigned.values() for fid in ids}
    auto: dict[int, list[str]] = {i: [] for i in range(len(plan))}
    orphans = []
    for f in findings:
        if f.id in linked:
            continue
        best = max(range(len(plan)), key=lambda i: _cos(vec_f[f.id], vec_plan[i]))
        if _cos(vec_f[f.id], vec_plan[best]) >= ATTACH_MIN:
            auto[best].append(f.id)
        else:
            orphans.append(f)

    # gravité de repli : celle de la recommandation entière (un sous-point sans constat lié ne doit pas passer
    # devant un sous-point appuyé par des constats : l'absence de preuve n'est pas une urgence)
    reco_sev = {r["id"]: max((SEV.get(f.severity, 0) for f in by_reco[r["id"]]), default=0) for r in recs}
    initiatives = []
    for i, (r, label, txt) in enumerate(plan):
        fids = assigned[i]
        own = max((SEV.get(fmap[x].severity, 0) for x in fids), default=0)
        sev = own or reco_sev.get(r["id"], 0)
        wave, reason = wave_for(r.get("deadline"), sev, today)
        if not own and sev:
            reason += " (aucun constat rattaché à ce point : gravité prise sur l'ensemble de la recommandation)"
        axis = f"R{r['number']} — {r['title']}" if r.get("number") else r["title"]
        scores = []
        if sev:
            scores.append(CriterionScore(key="impact", value={3: 5, 2: 3, 1: 2}[sev], source_ids=[],
                                         rationale=f"Gravité {SEV_FR[sev]} des constats liés"))
        d = parse_deadline(r.get("deadline"))
        if d:
            left = months_between(today, d)
            scores.append(CriterionScore(key="urgence", value=5 if left <= 6 else 4 if left <= 12 else 3,
                                         source_ids=[], rationale=f"Échéance du rapport : {r['deadline']}"[:160]))
        initiatives.append(Initiative(
            id=new_id("ini"), title=short_title(txt),
            description=(f"Recommandation n° {r['number']} — {label}) {txt}" if label
                         else f"Recommandation n° {r.get('number') or '–'} — {txt}"),
            finding_ids=fids + auto[i], scores=scores, objective=r.get("intro") or "", axis=axis,
            auto_finding_ids=auto[i], wave_reason=reason, deadline=r.get("deadline"),
            recommendation={"id": r["id"], "number": r.get("number"), "label": label, "title": r["title"],
                            "document_id": r.get("document_id"), "page": r.get("page"), "wave": wave}))
    warnings = []
    if orphans:
        warnings.append(f"{len(orphans)} constat(s) validé(s) sans recommandation liée ni initiative assez proche : "
                        "à rattacher à la main ou à écarter.")
    return initiatives, warnings, {"orphans": [f.id for f in orphans], "plan": len(plan)}
