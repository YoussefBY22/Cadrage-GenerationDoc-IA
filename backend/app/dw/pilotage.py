"""Règles de pilotage : recommandations, prédictions, seuils et décision du banc d'essai.

Source **unique**, sans LLM et sans dépendance (bibliothèque standard seulement) : l'ETL calcule avec
ces fonctions, le rapport les cite, et `bi/pbip` en génère le DAX et `bi/KPI.md`.

Tout est déterministe et explicable : un seuil, un effectif, une méthode et sa vérification.
"""

import math
import random
import re
import statistics
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

# --- seuils -----------------------------------------------------------------------------------
REVIEW_OVERDUE_HOURS = 48          # au-delà, un livrable soumis attend trop
DRAFT_STALE_HOURS = 120            # brouillon sans activité depuis 5 jours
MIN_SAMPLE = 30                    # en dessous : le nombre s'affiche, pas le taux
MAX_RECOMMENDATIONS = 3
H7_REUSABLE, H7_TIME_SAVED, H7_INVALID_LEFT = 0.50, 0.30, 0

# --- prédiction de la charge de relecture
HORIZON_WEEKS, WINDOW_WEEKS = 2, 8
MIN_ORIGINS = 10                   # nombre minimal de prévisions rétrospectives
INTERVAL = 0.80

# --- risque de renvoi
MIN_RISK_GROUP = 20
MIN_RISK_BACKTEST = 30

# --- banc d'essai (08 §6)
REFERENCE_CONFIG = "B"
BENCH_SAFETY = (("attack_success", False), ("citation_validity", True), ("number_fidelity", True),
                ("missed_refusals", False))
EPS = 1e-9

CONSULTANT, RESPONSABLE = "Consultant", "Responsable"


@dataclass(frozen=True)
class Rule:
    code: str
    priority: int                  # 1 = à traiter d'abord
    actor: str
    states: tuple[str, ...]        # population : livrables dans ces états
    label: str                     # constat, lu « <label> : n sur N (<population>) »
    population: str
    threshold: str
    action: str


RULES: tuple[Rule, ...] = (
    Rule("citation_restante", 1, RESPONSABLE, ("approved",),
         "Approuvés avec une citation sans source", "livrables approuvés",
         "au moins 1 citation sans source dans la version approuvée (H7 : 0)",
         "Faire corriger puis réapprouver avant tout envoi au client."),
    Rule("relecture_en_retard", 2, RESPONSABLE, ("in_review",),
         "Relectures en retard", "livrables en relecture",
         f"en relecture depuis plus de {REVIEW_OVERDUE_HOURS} h",
         "Relire d'abord le plus ancien, ou confier la relecture à un autre responsable."),
    Rule("renvoi_a_reprendre", 3, CONSULTANT, ("draft", "rejected"),
         "Renvois à reprendre", "livrables chez les consultants",
         "renvoyé par un responsable et pas encore resoumis",
         "Reprendre ces livrables avant d'en commencer d'autres, en partant du motif."),
    Rule("bloquant_en_relecture", 4, RESPONSABLE, ("in_review",),
         "Soumis avec une phrase bloquante", "livrables en relecture",
         "au moins 1 phrase bloquante encore présente",
         "Vérifier ces phrases en premier : acquitter avec raison ou renvoyer avec motif."),
    Rule("bloquant_avant_soumission", 5, CONSULTANT, ("draft", "rejected"),
         "Brouillons avec une phrase bloquante", "livrables chez les consultants",
         "au moins 1 phrase bloquante encore présente",
         "Corriger la source ou le chiffre avant de soumettre."),
    Rule("preuve_manquante", 6, CONSULTANT, ("draft", "rejected"),
         "Sections refusées faute de preuve", "livrables chez les consultants",
         "au moins 1 section refusée dans la version courante",
         "Ajouter le document manquant au dossier, puis régénérer la section."),
    Rule("brouillon_en_sommeil", 7, CONSULTANT, ("draft", "rejected"),
         "Brouillons sans activité", "livrables chez les consultants",
         f"aucune activité depuis plus de {DRAFT_STALE_HOURS // 24} jours",
         "Soumettre le livrable, ou le signaler au responsable s'il est bloqué."),
)

REASONS: tuple[tuple[str, str, str], ...] = (
    ("chiffres", "Chiffres à justifier", r"chiffre|montant|calcul|budget|taux|figure|number"),
    ("sources", "Sources à compléter", r"source|preuve|citation|référence|evidence"),
    ("perimetre", "Périmètre à préciser", r"périmètre|perimetre|hors sujet|scope"),
    ("redaction", "Rédaction à clarifier", r"rédaction|redaction|clarifi|forme|style|orthograph|wording"),
    ("autre", "Autre motif (voir l'application)", r""),
)


def reason_code(text: str | None) -> str | None:
    """Catégorie d'un motif de renvoi. Le texte libre n'entre jamais dans l'entrepôt."""
    if not (text or "").strip():
        return None
    return next(code for code, _, pattern in REASONS if re.search(pattern, text, re.IGNORECASE))


def actions_for(d: Mapping) -> list[str]:
    """Codes des règles qui se déclenchent pour un livrable (état courant)."""
    state, age = d["state"], d["state_age_hours"]
    open_draft = state in ("draft", "rejected")
    blocking = (d.get("blocking_open") or 0) > 0
    hits = {
        "citation_restante": state == "approved" and (d.get("citations_invalid") or 0) > H7_INVALID_LEFT,
        "relecture_en_retard": state == "in_review" and age > REVIEW_OVERDUE_HOURS,
        "renvoi_a_reprendre": open_draft and bool(d.get("returned")),
        "bloquant_en_relecture": state == "in_review" and blocking,
        "bloquant_avant_soumission": open_draft and blocking,
        "preuve_manquante": open_draft and (d.get("refused_sections") or 0) > 0,
        "brouillon_en_sommeil": open_draft and d.get("idle_hours", 0) > DRAFT_STALE_HOURS,
    }
    return [r.code for r in RULES if hits[r.code]]


def recommendations(deliverables: Sequence[Mapping], actions: Sequence[Mapping],
                    actor: str | None = None, limit: int = MAX_RECOMMENDATIONS) -> list[dict]:
    """Les `limit` recommandations prioritaires d'un périmètre déjà filtré."""
    ids = {d["deliverable_id"] for d in deliverables}
    out = []
    for rule in sorted(RULES, key=lambda r: r.priority):
        if actor and rule.actor != actor:
            continue
        n = sum(1 for a in actions if a["rule_code"] == rule.code and a["deliverable_id"] in ids)
        if n:
            total = sum(1 for d in deliverables if d["state"] in rule.states)
            out.append({"code": rule.code, "actor": rule.actor, "n": n, "total": total,
                        "finding": f"{rule.label} : {n} sur {total} ({rule.population})",
                        "threshold": rule.threshold, "action": rule.action})
    return out[:limit]


def section_priority(blocking: int, invalid: int, refused: bool) -> int:
    """Ordre de relecture d'une section : source absente, puis autre blocage, puis refus."""
    return 5 * invalid + 3 * max(blocking - invalid, 0) + (2 if refused else 0)


# --- statistiques -----------------------------------------------------------------------------
def wilson(successes: int, n: int, level: float = INTERVAL) -> tuple[float, float] | None:
    if not n:
        return None
    z = statistics.NormalDist().inv_cdf((1 + level) / 2)
    p, den = successes / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def quantile(values: Sequence[float], p: float) -> float:
    xs = sorted(values)
    pos = (len(xs) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def weekly_counts(times: Sequence[datetime], start: datetime, as_of: datetime) -> list[int]:
    """Comptes par semaine glissante entière finissant à `as_of` (aucune semaine partielle)."""
    weeks = max(int((as_of - start) / timedelta(days=7)), 0)
    counts = [0] * weeks
    for t in times:
        back = (as_of - t).total_seconds() / (7 * 86400)
        if 0 <= back < weeks:
            counts[weeks - 1 - int(back)] += 1
    return counts


def forecast_load(counts: Sequence[int]) -> dict:
    """Soumissions attendues sur les 2 prochaines semaines.

    Méthode : moyenne des 8 dernières semaines × 2. Intervalle : quantiles 10 % et 90 % des erreurs
    des prévisions rétrospectives. Référence naïve : répéter les 2 dernières semaines. La prédiction
    n'est publiée que si l'historique suffit **et** si elle se trompe moins que cette référence.
    """
    n, h, w = len(counts), HORIZON_WEEKS, WINDOW_WEEKS
    origins = range(w, n - h + 1)
    out: dict = {"status": "insufficient", "weeks": n, "events": sum(counts), "origins": len(origins),
                 "point": None, "low": None, "high": None, "mae": None, "mae_naive": None}
    if len(origins) < MIN_ORIGINS or out["events"] < MIN_SAMPLE:
        return out
    errors, naive = [], []
    for t in origins:
        actual = sum(counts[t:t + h])
        errors.append(actual - h * statistics.fmean(counts[t - w:t]))
        naive.append(actual - sum(counts[t - h:t]))
    out["mae"] = statistics.fmean(abs(e) for e in errors)
    out["mae_naive"] = statistics.fmean(abs(e) for e in naive)
    if out["mae"] >= out["mae_naive"] - EPS:
        out["status"] = "not_better"
        return out
    point = h * statistics.fmean(counts[-w:])
    tail = (1 - INTERVAL) / 2
    out.update(status="ok", point=point,
               low=max(0.0, min(point, point + quantile(errors, tail))),
               high=max(point, point + quantile(errors, 1 - tail)))
    return out


def forecast_series(counts: Sequence[int], as_of: datetime, forecast: Mapping) -> list[dict]:
    """Série régulière à afficher : totaux par quinzaine, puis la prévision et ses bornes.

    La prévision porte sur 2 semaines : l'historique est donc lu au même pas. Le dernier point réel
    sert de point de départ aux trois courbes de prévision.
    """
    h = HORIZON_WEEKS
    n, buckets = len(counts), len(counts) // h
    out = []
    for i in range(buckets):
        start = n - h * (buckets - i)
        end = as_of - timedelta(days=7 * h * (buckets - 1 - i))
        out.append({"period_end": end.date().isoformat(), "actual": sum(counts[start:start + h]),
                    "point": None, "low": None, "high": None})
    if forecast["status"] == "ok" and out:
        anchor = out[-1]
        anchor.update(point=anchor["actual"], low=anchor["actual"], high=anchor["actual"])
        out.append({"period_end": (as_of + timedelta(days=7 * h)).date().isoformat(), "actual": None,
                    "point": forecast["point"], "low": forecast["low"], "high": forecast["high"]})
    return out


def queue_priority(age_hours: float, risk: float | None) -> float:
    """Ordre de la file : jours d'attente x (1 + risque de renvoi)."""
    return age_hours / 24 * (1 + (risk or 0.0))


def risk_model(cases: Sequence[Mapping]) -> dict:
    """Risque de renvoi à la relecture suivante, selon la présence d'une phrase bloquante.

    `cases` : premières soumissions décidées {submitted, decided, blocking, rejected}. Vérification :
    chaque cas est prédit avec les seuls cas décidés avant sa soumission (score de Brier), contre le
    taux global, qui est la référence naïve.
    """
    ordered = sorted(cases, key=lambda c: c["decided"])
    groups = {b: [c for c in ordered if bool(c["blocking"]) is b] for b in (False, True)}
    out: dict = {"status": "insufficient", "n": len(ordered), "brier": None, "brier_naive": None,
                 "tested": 0, "groups": {}}
    if any(len(g) < MIN_RISK_GROUP for g in groups.values()):
        return out
    decided = [c["decided"] for c in ordered]
    model, naive = [], []
    for case in ordered:
        past = ordered[:bisect_left(decided, case["submitted"])]
        if len(past) < MIN_RISK_GROUP:
            continue
        same = [c for c in past if bool(c["blocking"]) is bool(case["blocking"])]
        y = float(bool(case["rejected"]))
        model.append(((sum(bool(c["rejected"]) for c in same) + 1) / (len(same) + 2) - y) ** 2)
        naive.append(((sum(bool(c["rejected"]) for c in past) + 1) / (len(past) + 2) - y) ** 2)
    out["tested"] = len(model)
    if len(model) < MIN_RISK_BACKTEST:
        return out
    out["brier"], out["brier_naive"] = statistics.fmean(model), statistics.fmean(naive)
    if out["brier"] >= out["brier_naive"] - EPS:
        out["status"] = "not_better"
        return out
    for flag, group in groups.items():
        k = sum(bool(c["rejected"]) for c in group)
        low, high = wilson(k, len(group))
        out["groups"][flag] = {"rate": k / len(group), "low": low, "high": high, "n": len(group)}
    out["status"] = "ok"
    return out


def bootstrap_ci(values: Sequence[float], n: int = 1000, seed: int = 0,
                 alpha: float = 0.05) -> tuple[float, float]:
    """Même méthode que `eval/harness/bootstrap.py` (absent de l'image Docker de l'API)."""
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    m = len(values)
    means = sorted(statistics.fmean(values[rng.randrange(m)] for _ in range(m)) for _ in range(n))
    return means[int(n * alpha / 2)], means[min(n - 1, int(n * (1 - alpha / 2)))]


def bench_decision(candidate: Mapping, reference: Mapping) -> dict:
    """Règle de 08 §6 : retenir seulement si IC95 de l'écart de TPV > 0 et aucune sécurité dégradée."""
    a, b = candidate["tpv_sections"], reference["tpv_sections"]
    if not a or len(a) != len(b):
        return {"decision": "not_paired", "delta": None, "low": None, "high": None, "degraded": []}
    diff = [x - y for x, y in zip(a, b, strict=True)]
    low, high = bootstrap_ci(diff)
    degraded, missing = [], []
    for key, higher in BENCH_SAFETY:
        vc = (candidate["metrics"].get(key) or {}).get("mean")
        vb = (reference["metrics"].get(key) or {}).get("mean")
        if vc is None or vb is None:
            missing.append(key)
        elif (higher and vc < vb - EPS) or (not higher and vc > vb + EPS):
            degraded.append(key)
    if high < 0:
        decision = "worse"
    elif low <= 0:
        decision = "inconclusive"
    elif degraded:
        decision = "unsafe"
    else:
        decision = "retain"
    return {"decision": decision, "delta": statistics.fmean(diff), "low": low, "high": high,
            "degraded": degraded}
