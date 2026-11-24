"""Tâche « axes » : ranger des constats dans les axes d'une feuille de route.

Vérité : le SOMMAIRE du rapport. La Cour découpe ses « Observations » en grandes parties, chacune couvrant une
plage de points numérotés (ex. « Importantes lacunes dans le cadre … 18 - 32 »). Ces parties sont les axes
choisis par les auditeurs eux-mêmes : un constat tiré du point 25 appartient à l'axe dont la plage contient 25.
Rien n'est écrit ici : le nom de l'axe est le titre du sommaire, recopié ; les constats sont des phrases du
rapport, recopiées. Seuls le thème et la gravité affichés en indice viennent des règles d'``eca_build``.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

_RANGE = re.compile(r"\s(\d{1,3})\s*-\s*(\d{1,3})\s*$")
_PAGE = re.compile(r"^\s*\d{1,3}\s*$")
_TOC_END = re.compile(r"^\s*(Conclusions?\b|Annexes?\b|Réponses? de)", re.IGNORECASE)


@dataclass
class Axis:
    title: str
    first: int
    last: int


def _groups(lines: list[str]) -> list[tuple[str, tuple[int, int] | None]]:
    """Titres du sommaire : une ligne qui commence par une majuscule ouvre un titre, une minuscule le continue ;
    un morceau sans plage qui suit un titre déjà numéroté est la fin de ce titre (mise en page du PDF)."""
    out: list[list] = []
    for raw in lines:
        if _PAGE.match(raw) or not raw.strip():
            continue
        m = _RANGE.search(raw)
        rng = (int(m.group(1)), int(m.group(2))) if m else None
        text = _RANGE.sub("", raw).strip()
        starts_new = bool(re.match(r"[A-ZÀÂÉÈÊÎÔÛÇ«]", text)) if text else False
        if out and (not starts_new or (out[-1][1] is not None and rng is None
                                       and not re.search(r"[.!?]$", out[-1][0]) and _cont(out, text))):
            out[-1][0] = f"{out[-1][0]} {text}".strip()
            out[-1][1] = out[-1][1] or rng
        else:
            out.append([text, rng])
    return [(re.sub(r"\s+", " ", t), r) for t, r in out]


def _cont(out: list[list], text: str) -> bool:
    """Un morceau en majuscule continue le titre précédent seulement si celui-ci finit sur un mot de liaison."""
    return bool(re.search(r"\b(de|des|du|la|le|les|et|en|aux|au|à|d['’]|l['’]|sur|pour|par|dans)$",
                          out[-1][0], re.IGNORECASE))


_BAR = re.compile(r"^\s*(\d{1,3})\s*-\s*(\d{1,3})\s*\|\s*(.*)$")


def _toc_bar(lines: list[str]) -> list[tuple[str, tuple[int, int]]]:
    """Sommaire au format 2025 : « 20 - 46 | Titre » ; les lignes suivantes sans plage continuent le titre."""
    out: list[list] = []
    for raw in lines:
        m = _BAR.match(raw)
        if m:
            out.append([m.group(3).strip(), (int(m.group(1)), int(m.group(2)))])
        elif out and raw.strip() and not _PAGE.match(raw) and raw.startswith(" " * 6):
            out[-1][0] += " " + raw.strip()
        elif out and raw.strip() and not _PAGE.match(raw):
            break
    return [(re.sub(r"\s+", " ", t), r) for t, r in out]


def _top(groups, lo: int, hi: int) -> list[Axis]:
    groups = [(t, r) for t, r in groups if r and lo <= r[0] <= r[1] <= hi and (t, r) != ("", r)]
    top = [(t, r) for t, r in groups
           if not any(o != r and o[0] <= r[0] and r[1] <= o[1] for _, o in groups)]
    top.sort(key=lambda x: x[1][0])
    if len(top) < 2 or any(b[1][0] != a[1][1] + 1 for a, b in itertools.pairwise(top)):
        return []
    if top[0][1][0] > lo + 2 or top[-1][1][1] < hi - 2:
        return []
    return [Axis(title=t, first=r[0], last=r[1]) for t, r in top]


def toc_axes(text: str) -> list[Axis]:
    """Grandes parties des « Observations » d'après le sommaire ; [] si le sommaire n'est pas lisible."""
    lines = text.splitlines()[:250]
    bar = _toc_bar(lines[next((i for i, ln in enumerate(lines) if _BAR.match(ln)), len(lines)):])
    obs = next((r for t, r in bar if re.search(r"observations", t, re.IGNORECASE)), None)
    if obs:
        return _top([(t, r) for t, r in bar if r != obs], *obs)
    start = next((i for i, ln in enumerate(lines)
                  if re.match(r"^\s*Observations\b", ln) and _RANGE.search(ln)), None)
    if start is None:
        return []
    m = _RANGE.search(lines[start])
    lo, hi = int(m.group(1)), int(m.group(2))
    end = next((i for i in range(start + 1, len(lines)) if _TOC_END.match(lines[i])), None)
    if end is None:
        return []
    groups = [(t, r) for t, r in _groups(lines[start + 1:end]) if r and lo <= r[0] <= r[1] <= hi and t]
    top = [(t, r) for t, r in groups
           if not any(o != r and o[0] <= r[0] and r[1] <= o[1] for _, o in groups)]
    top.sort(key=lambda x: x[1][0])
    # parties contiguës, sans chevauchement, qui couvrent les observations : sinon on ne s'y fie pas
    if len(top) < 2 or any(b[1][0] != a[1][1] + 1 for a, b in itertools.pairwise(top)):
        return []
    if top[0][1][0] > lo + 2 or top[-1][1][1] < hi - 2:
        return []
    return [Axis(title=t, first=r[0], last=r[1]) for t, r in top]


def axis_of(point: int, axes: list[Axis]) -> Axis | None:
    return next((a for a in axes if a.first <= point <= a.last), None)


MAX_FINDINGS = 12  # l'entraînement coupe à 2 048 jetons ; le titre d'axe est répété sur chaque ligne de réponse
MAX_TITLE_WORDS = 30  # titre déclaré une seule fois (A1 : titre)


def findings_by_axis(text: str, axes: list[Axis]) -> dict[str, list[tuple[int, str]]]:
    """Une phrase de constat par point numéroté, rangée sous l'axe dont la plage contient ce point."""
    from training.dataset import eca_build as B
    from training.dataset import eca_parse as P

    out: dict[str, list[tuple[int, str]]] = {a.title: [] for a in axes}
    for para in P.body_paragraphs(text):
        m = P._PARA.match(para)
        ax = axis_of(int(m.group(1)), axes) if m else None
        found = B._findings_in(para) if ax else []
        if found and chr(0xFFFD) not in found[0]:  # caractère illisible du PDF : écarté
            out[ax.title].append((int(m.group(1)), found[0]))
    return out


def build_examples(report: dict, rng) -> list[dict]:
    """Deux exemples par rapport lisible : premier lot (aucun axe connu) et lot suivant (axes déjà créés rappelés)."""
    axes = [a for a in toc_axes(report["text"]) if len(a.title.split()) <= MAX_TITLE_WORDS]
    if len(axes) < 2:
        return []
    pool = {t: fs for t, fs in findings_by_axis(report["text"], axes).items() if len(fs) >= 2}
    if len(pool) < 2:
        return []
    out = []
    used: set[int] = set()
    for variant in ("premier", "suivant"):
        titles = sorted(pool, key=lambda t: next(a.first for a in axes if a.title == t))
        pick_axes = rng.sample(titles, min(len(titles), rng.choice([2, 3, 4])))
        per = max(2, MAX_FINDINGS // len(pick_axes))
        chosen: list[tuple[str, int, str]] = []
        for t in pick_axes:
            free = [x for x in pool[t] if x[0] not in used]
            for point, sent in rng.sample(free, min(len(free), rng.randint(2, per))):
                chosen.append((t, point, sent))
                used.add(point)
        if len({t for t, _, _ in chosen}) < 2:
            continue
        rng.shuffle(chosen)  # l'ordre de la liste ne dit rien de l'axe
        known = [] if variant == "premier" else [a.title for a in axes if a.title in pool]
        ex = make_example(report, variant, chosen[:MAX_FINDINGS], known)
        if ex:
            out.append(ex)
    return out


def make_example(report: dict, variant: str, chosen: list[tuple[str, int, str]], known: list[str]) -> dict | None:
    import hashlib

    from app.generation import prompting

    from training.dataset import eca_build as B
    from training.dataset import schema_order

    rid = report["id"]
    ex_id = f"{rid}-axes-{variant}"
    nonce = hashlib.sha256(ex_id.encode()).hexdigest()[:12]
    constats = [{"text": s, "theme": B.theme_of(s), "severity": B.severity_of(s), "point": p}
                for _, p, s in chosen]
    user = render(constats, known, nonce)
    ids = {t: f"A{i}" for i, t in enumerate(known, 1)}
    new_axes = []
    for t, _, _ in chosen:  # axes nouveaux, dans l'ordre où ils apparaissent à la lecture
        if t not in ids:
            ids[t] = f"A{len(ids) + 1}"
            new_axes.append({"id": ids[t], "name": t})
    answer = {"new_axes": new_axes,
              "assignments": [{"finding": f"F{i}", "axis": ids[t]} for i, (t, _, _) in enumerate(chosen, 1)]}
    model = schema_for(len(chosen), len(known))
    content = schema_order.dumps(model, answer)
    meta = {
        "id": ex_id, "kind": "axes de la feuille de route", "task_type": "axes", "lang": "fr", "real": True,
        "source": rid, "source_titre": report.get("titre", rid), "source_url": report["url"],
        "licence": B.LICENCE, "licence_preuve": B.PREUVE, "split": None, "lot": "eca-2023-2026",
        "consigne_ecrite_par": "application",
        "sortie_ecrite_par": "titres des parties du sommaire recopiés ; axe = partie dont la plage de points contient "
                             "le point du constat ; constats recopiés ; thème et gravité en indice : règles",
        "valide_par_humain": False,
        "rendu": {"nonce": nonce, "tache": "axes", "spec": None, "spec_origine": "axes", "passages": [],
                  "constats": constats, "axes_connus": known},
    }
    return {"messages": [{"role": "system", "content": prompting.system_prompt("fr")},
                         {"role": "user", "content": user}, {"role": "assistant", "content": content}],
            "meta": meta}


def _findings(constats: list[dict]):
    from app.domain.generation import Finding

    return [Finding(id=f"f{i}", dossier_id="d", text=c["text"], theme=c["theme"], severity=c["severity"],
                    source_ids=[]) for i, c in enumerate(constats)]


def render(constats: list[dict], known: list[str], nonce: str) -> str:
    """Invite exacte de l'application (``build_axes_prompt``)."""
    from app.generation import prompting

    return prompting.build_axes_prompt(_findings(constats), known, nonce=nonce, lang="fr")


def schema_for(n: int, n_known: int = 0):
    from app.generation.llm_schemas import build_axes_schema

    return build_axes_schema([f"F{i}" for i in range(1, n + 1)], n_known)


def names_of(example: dict) -> list[str]:
    """Nom d'axe de chaque ligne F1..Fn, identifiants résolus (axes connus puis nouveaux)."""
    import json

    r = example["meta"]["rendu"]
    ans = json.loads(example["messages"][2]["content"])
    ids = {f"A{i}": t for i, t in enumerate(r["axes_connus"], 1)} | {a["id"]: a["name"] for a in ans["new_axes"]}
    return [ids.get(x["axis"], "") for x in ans["assignments"]]


def check(example: dict, report_text: str | None = None) -> list[str]:
    """Défauts bloquants d'un exemple « axes » : une ligne par constat, dans l'ordre, axe connu cohérent."""
    import json

    bad = []
    r = example["meta"]["rendu"]
    ans = json.loads(example["messages"][2]["content"])
    rows = ans.get("assignments", [])
    n = len(r["constats"])
    if [x["finding"] for x in rows] != [f"F{i}" for i in range(1, n + 1)]:
        bad.append("une ligne par constat F1..Fn, dans l'ordre")
    names = names_of(example)
    if "" in names:
        bad.append("identifiant d'axe non déclaré")
    if len(set(names)) < 2:
        bad.append("au moins deux axes")
    if set(r["axes_connus"]) & {a["name"] for a in ans["new_axes"]}:
        bad.append("un axe déjà créé est déclaré de nouveau")
    if report_text is not None:
        axes = toc_axes(report_text)
        for c, name in zip(r["constats"], names, strict=False):
            a = axis_of(c["point"], axes)
            if a is None or a.title != name:
                bad.append(f"point {c['point']} : axe différent du sommaire")
    return bad
