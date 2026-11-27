"""Feuille de route : constats validés → initiatives notées → priorité, vagues, chemin critique."""

import re

from app.domain.generation import DeliverableContent
from app.domain.ids import new_id
from app.domain.retrieval import Passage
from app.domain.roadmap import (
    Criterion,
    CriterionScore,
    Initiative,
    RejectedLink,
    RoadmapResult,
)
from app.domain.workflow import CurrentUser
from app.generation.llm_schemas import LLMAxisName, build_initiatives_schema
from app.generation.prompting import (
    build_axis_name_prompt,
    build_initiatives_prompt,
    fit_passages,
    passage_budget,
    safe_tokens,
    system_prompt,
)
from app.generation.template_loader import load_template
from app.llm.base import LLMProvider
from app.roadmap import axes as axes_mod
from app.roadmap import coherence as coh
from app.roadmap import graph, proposals, scoring

from . import context_sheet
from .generation import GenerationError, call_model, get_deliverable, new_nonce, record_run

MAX_PASSAGES = 30
ROADMAP_REPLY_TOKENS = 1800  # mesuré : 3 initiatives notées ≈ 1 500 jetons de réponse
MAX_FINDINGS_PER_CALL = 8  # réponse courte : quelques initiatives par appel, jamais tronquée
SMALL_ROADMAP = 8  # jusqu'à 8 constats distincts : un seul appel, sans étape « axes »


def _lbl(x: str) -> str:
    return re.sub(r"\W", "", x).upper()


def _echo(title: str) -> bool:
    """Titre qui recopie la consigne (étiquettes, critères) ou qui est une phrase-fleuve : ce n'est pas un titre."""
    low = title.lower()
    return ("f1..fn" in low or "notées de 1 à 5" in low or "scored 1 to 5" in low or "cite f1" in low
            or len(title.split()) > 25)


def _title_key(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())


def compute(initiatives: list[Initiative], criteria: list[Criterion], waves: int,
            findings=(), priorities=()) -> tuple[RoadmapResult, list[str]]:
    """Calcul déterministe, sans modèle : score, rang, vagues, ordre topologique, cycles.

    Les égalités de score sont départagées par une règle explicite (coherence.tiebreak_keys).
    """
    tb = coh.tiebreak_keys(initiatives, list(findings), list(priorities))
    items, warnings = scoring.score_with_warnings(initiatives, criteria, waves, tiebreak=tb)
    topo, cycles, critical = graph.analyze(initiatives)
    return RoadmapResult(criteria=criteria, items=items, topo_order=topo, cycles=cycles,
                         critical_path=critical), warnings


def _fixed_prompt(findings, criteria, priorities, projects, nonce, language, axis):
    return system_prompt(language) + build_initiatives_prompt(
        findings, [], criteria, nonce=nonce, lang=language, priorities=priorities, projects=projects,
        axis=axis)


def _fits(ctx_tokens, findings, criteria, priorities, projects, nonce, language, axis) -> bool:
    if not ctx_tokens:
        return True
    fixed = _fixed_prompt(findings, criteria, priorities, projects, nonce, language, axis)
    return safe_tokens(fixed) + ROADMAP_REPLY_TOKENS + 64 <= ctx_tokens


def _split_to_fit(group, fits) -> list[list]:
    """Découpe un axe en parties qui tiennent dans la fenêtre (ordre conservé, rien d'abandonné)."""
    parts, cur = [], []
    for f in group:
        if cur and (len(cur) >= MAX_FINDINGS_PER_CALL or not fits(cur + [f])):
            parts.append(cur)
            cur = []
        cur.append(f)
    if cur:
        parts.append(cur)
    return parts


def _group_by_meaning(repo, provider, dossier_id, reps, language) -> tuple[list, list[str], int, str]:
    """Étape 1 : les constats sont rangés en axes PAR LE CODE, d'après leur sens (vecteurs bge-m3).

    Axes imposés par le consultant (fiche de contexte confirmée) : chaque constat va à l'axe le plus proche.
    Sinon : regroupement hiérarchique en 2 à 6 groupes, puis le modèle donne un nom court à chaque groupe.
    Le test v5 a montré qu'un modèle de 4 milliards de paramètres range mal ses constats (57 % des paires) :
    le code range, le modèle nomme.
    """
    sheet = context_sheet.get(repo, dossier_id)
    imposed = axes_mod.parse_axes(sheet.data.roadmap_axes) if sheet.confirmed else []
    vectors = provider.embed([f.text for f in reps])
    if imposed:
        idx = axes_mod.nearest(vectors, provider.embed(imposed))
        groups = [(imposed[a], [f for f, x in zip(reps, idx, strict=True) if x == a]) for a in range(len(imposed))]
        return [(n, g) for n, g in groups if g], [], 0, "imposés"
    nonce = new_nonce()
    names: list[str] = []
    errors: list[str] = []
    calls = 0
    out = []
    for members in axes_mod.cluster_balanced(vectors, axes_mod.k_for(len(reps))):
        group = [reps[i] for i in members]
        sample = [reps[i] for i in axes_mod.central(vectors, members, 10)]
        prompt = build_axis_name_prompt(sample, names, nonce=nonce, lang=language)
        from . import jobs
        jobs.current().step(f"Le modèle nomme l'axe n° {len(names) + 1} ({len(group)} constats)")
        llm, attempts, latency, error = call_model(provider, prompt, LLMAxisName, lang=language)
        calls += 1
        record_run(repo, provider, dossier_id=dossier_id, kind="axes", prompt=prompt,
                   status="ok" if llm else "invalid", attempts=attempts, latency_ms=latency,
                   output=llm.model_dump_json() if llm else "")
        name = (llm.name.strip() if llm else "")[:120]
        if not name or axes_mod.axis_key(name) in {axes_mod.axis_key(x) for x in names}:
            if llm is None:
                errors.append(error or "")
            name = axes_mod.majority_theme(group) or f"Axe {len(names) + 1}"
            if axes_mod.axis_key(name) in {axes_mod.axis_key(x) for x in names}:
                name = f"{name} ({len(names) + 1})"
        names.append(name)
        out.append((name, group))
    return out, errors, calls, "par le sens"


def _attach_orphans(provider, initiatives: list, groups: list, dups: dict, fmap: dict) -> list:
    """Constat qu'aucune initiative ne traite : rattaché à l'initiative de SON axe la plus proche par le sens.

    Mesuré sur un vrai rapport : 11 constats sur 74 restaient orphelins. Le lien est marqué (auto_finding_ids) :
    c'est une proposition du code, que le consultant vérifie ; jamais un constat n'est inventé ni retiré.
    """
    covered = {f for ini in initiatives for f in ini.finding_ids}
    axis_of = {f.id: axis for axis, group in groups for f in group}
    orphans = [f for axis, group in groups for f in group if f.id not in covered]
    if not orphans or not initiatives:
        return initiatives
    texts = {ini.id: " ".join(fmap[i].text for i in ini.finding_ids if i in fmap)[:2000] or ini.title
             for ini in initiatives}
    ids = list(texts)
    ivec = dict(zip(ids, provider.embed([texts[i] for i in ids]), strict=True))
    ovec = provider.embed([f.text for f in orphans])
    extra: dict[str, list[str]] = {}
    for f, v in zip(orphans, ovec, strict=True):
        same = [ini for ini in initiatives if ini.axis == axis_of.get(f.id)] or initiatives
        best = max(same, key=lambda ini: axes_mod._cos(v, ivec[ini.id]))
        extra.setdefault(best.id, []).extend([f.id, *dups.get(f.id, [])])
    return [ini.model_copy(update={"finding_ids": list(dict.fromkeys(ini.finding_ids + extra.get(ini.id, []))),
                                   "auto_finding_ids": extra.get(ini.id, [])}) for ini in initiatives]


def generate(repo, provider: LLMProvider, dossier_id: str, user: CurrentUser, *,
             criteria: list[Criterion] | None = None, waves: int = 3,
             language: str = "fr", mode: str = "auto") -> dict:
    """Feuille de route par axes.

    Peu de constats : un seul appel, comme avant. Sinon, comme un cabinet de conseil : (1) doublons fusionnés,
    (2) le modèle range les constats en axes par petits lots, (3) les initiatives sont proposées axe par axe
    (un axe trop gros est découpé), (4) le calcul sans modèle classe tout et répartit en vagues. Chaque appel
    tient dans la fenêtre : un rapport de 100 pages passe comme un petit, en plus d'appels.
    """
    findings = repo.list_findings(dossier_id, validated_only=True)
    if not findings:
        raise GenerationError(409, "NO_VALIDATED_FINDINGS",
                              "Validez d'abord des constats avant de générer la feuille de route")
    criteria = criteria or scoring.DEFAULT_CRITERIA
    priorities = repo.list_priorities(dossier_id, "validated")  # seules les validées servent
    projects = repo.list_projects(dossier_id)
    if mode in ("auto", "recommendations"):
        out = _from_recommendations(repo, provider, dossier_id, user, findings, criteria, waves, priorities,
                                    language)
        if out is not None:
            return out
        if mode == "recommendations":
            raise GenerationError(409, "NO_RECOMMENDATIONS",
                                  "Aucune recommandation retenue dans les rapports : relevez-les d'abord, "
                                  "ou générez la feuille de route par le sens des constats.")
    ctx_tokens = getattr(provider, "context_tokens", None)
    nonce = new_nonce()

    from . import jobs
    job = jobs.current()
    reps, dups = axes_mod.dedupe(findings)
    job.step(f"{len(findings)} constats validés ; {len(findings) - len(reps)} doublon(s) fusionné(s) → {len(reps)} à traiter")
    fixed1 = _fixed_prompt(reps[:1], criteria, priorities, projects, nonce, language, "x" * 40)
    if ctx_tokens and safe_tokens(fixed1) + ROADMAP_REPLY_TOKENS + 64 > ctx_tokens:
        raise GenerationError(
            409, "CONTEXT_FULL",
            f"Priorités et projets (~{safe_tokens(fixed1)} jetons) ne tiennent pas dans la "
            f"fenêtre du modèle ({ctx_tokens}), même avec un seul constat : réduisez-les ou choisissez un "
            "modèle à plus grande fenêtre. Rien n'a été coupé.")
    sheet = context_sheet.get(repo, dossier_id)
    imposed = sheet.confirmed and bool(axes_mod.parse_axes(sheet.data.roadmap_axes))
    direct = not imposed and len(reps) <= SMALL_ROADMAP and _fits(ctx_tokens, reps, criteria, priorities, projects,
                                                  nonce, language, None)
    axis_errors: list[str] = []
    axis_calls = 0
    axis_mode = "direct"
    if direct:
        groups: list[tuple[str | None, list]] = [(None, reps)]
    else:
        job.step("Regroupement des constats par le sens, puis le modèle nomme chaque axe")
        groups, axis_errors, axis_calls, axis_mode = _group_by_meaning(repo, provider, dossier_id, reps,
                                                                      language)

    rejected: list[RejectedLink] = []
    not_sent = 0
    run_ids: list[str] = []
    part_errors: list[str] = []
    failed_findings: list[str] = []
    drafts: list[tuple[Initiative, list[str]]] = []
    fmap = {f.id: f for f in findings}
    planned = []
    for axis, group in groups:
        def fits(part, axis=axis):
            return _fits(ctx_tokens, part, criteria, priorities, projects, nonce, language, axis)

        planned += [(axis, part) for part in _split_to_fit(group, fits)]
    if not direct:
        job.step(f"{len(groups)} axe(s) : " + " ; ".join(f"{a} ({len(g)})" for a, g in groups))
    job.total(len(planned), "lots de constats")
    for n_part, (axis, part) in enumerate(planned, 1):
        job.step(f"Lot {n_part}/{len(planned)} — axe « {axis or 'unique'} » : le modèle propose des initiatives "
                 f"pour {len(part)} constat(s)")
        if True:
            # une partie ratée est coupée en deux et reprise une fois ; sinon signalée, sans effacer les autres
            pending = [(part, 0)]
            while pending:
                chunk, depth = pending.pop(0)
                try:
                    d, rj, ns, rid = _propose(repo, provider, dossier_id, chunk, criteria, priorities,
                                              projects, language, axis, ctx_tokens)
                except GenerationError as exc:
                    if depth == 0 and len(chunk) > 1:
                        half = len(chunk) // 2
                        pending += [(chunk[:half], 1), (chunk[half:], 1)]
                        continue
                    part_errors.append(f"{axis or '-'} : {exc.message}"[:300])
                    failed_findings += [f.id for f in chunk]
                    continue
                drafts += d
                rejected += rj
                not_sent += ns
                run_ids.append(rid)
                job.step(f"Lot {n_part} : {len(d)} initiative(s) proposée(s)")
        job.advance()

    job.step("Classement des initiatives, chemin critique et répartition en vagues (calcul, sans modèle)")
    # Doublons : ils suivent leur représentant. Même titre (deux axes ou deux parties) : une seule initiative.
    merged: dict[str, tuple[Initiative, list[str]]] = {}
    for ini, deps in drafts:
        fids = list(dict.fromkeys(x for i in ini.finding_ids for x in [i, *dups.get(i, [])]))
        axis = ini.axis or axes_mod.majority_theme([fmap[i] for i in fids if i in fmap])
        ini = ini.model_copy(update={"finding_ids": fids, "axis": axis})
        key = _title_key(ini.title)
        if key in merged:
            old, odeps = merged[key]
            merged[key] = (old.model_copy(update={
                "finding_ids": list(dict.fromkeys(old.finding_ids + ini.finding_ids)),
                "priority_ids": list(dict.fromkeys(old.priority_ids + ini.priority_ids)),
                "depends_on_projects": list(dict.fromkeys(old.depends_on_projects
                                                          + ini.depends_on_projects)),
                "proposal_flags": list(dict.fromkeys(old.proposal_flags + ini.proposal_flags))}),
                list(dict.fromkeys(odeps + deps)))
        else:
            merged[key] = (ini, deps)
    by_title = {_title_key(i.title): i.id for i, _ in merged.values()}
    initiatives = []
    for ini, deps in merged.values():
        dep_ids = []
        for t_ in deps:
            hit = by_title.get(_title_key(t_))
            if hit is None:
                rejected.append(RejectedLink(initiative=ini.title, kind="initiative", value=t_))
            elif hit != ini.id:
                dep_ids.append(hit)
        initiatives.append(ini.model_copy(update={"depends_on": list(dict.fromkeys(dep_ids))}))
    if not initiatives and (part_errors or axis_errors):
        raise GenerationError(502, "MODEL_INVALID",
                              f"Réponse du modèle invalide : {(part_errors or axis_errors)[0]}")
    initiatives = _attach_orphans(provider, initiatives, groups, dups, fmap)
    run_id = run_ids[0] if run_ids else None
    result, warnings = compute(initiatives, criteria, waves, findings, priorities)
    result = result.model_copy(update={"rejected_links": rejected, "passages_not_sent": not_sent})

    template = load_template("roadmap", language)
    did = repo.create_deliverable(dossier_id, "roadmap", template.id, user.id)
    version = repo.add_version(did, DeliverableContent(
        type="roadmap", language=language, template_id=template.id,
        template_version=template.version, sections=[], roadmap=result), user.id, "generated")
    repo.audit(user.id, "roadmap.generate", "deliverable", did,
               {"initiatives": len(initiatives), "run_id": run_id, "model": provider.served_model,
                "rejected_links": len(rejected), "passages_not_sent": not_sent,
                "priorities": len(priorities), "projects": len(projects),
                "axes": sorted({i.axis for i in initiatives if i.axis}),
                "model_calls": axis_calls + len(run_ids),
                "duplicates_merged": sum(len(v) for v in dups.values()),
                "axis_errors": len(axis_errors), "part_errors": part_errors, "axis_mode": axis_mode})
    return {"deliverable_id": did, "version": version, "warnings": warnings + [f"Partie non générée, constats à reprendre : {e}" for e in part_errors] + [f"Nom d'axe donné par défaut (modèle en échec) : {e}" for e in axis_errors],
            "roadmap": result.model_dump(mode="json"),
            "coherence": coherence_of(repo, dossier_id, result).model_dump(mode="json")}


def _propose(repo, provider, dossier_id, findings, criteria, priorities, projects, language, axis,
             ctx_tokens):
    """Un appel « initiatives » sur un sous-ensemble de constats (un axe, ou une partie d'axe)."""
    nonce = new_nonce()
    all_ids = list(dict.fromkeys(i for f in findings for i in f.source_ids))
    ids = all_ids[:MAX_PASSAGES]
    chunks = repo.get_chunks(dossier_id, ids)
    passages = [Passage(label=f"P{n}", chunk=chunks[i], score=0.0, ranks={})
                for n, i in enumerate((i for i in ids if i in chunks), 1)]
    fixed = _fixed_prompt(findings, criteria, priorities, projects, nonce, language, axis)
    budget = passage_budget(ctx_tokens, fixed, ROADMAP_REPLY_TOKENS)
    passages = fit_passages(passages, nonce, budget)  # seuls les passages lus sont citables
    not_sent = len(all_ids) - len(passages)  # coupe par le plafond ou la fenêtre : jamais silencieuse
    prompt = build_initiatives_prompt(findings, passages, criteria, nonce=nonce, budget=budget,
                                      lang=language, priorities=priorities, projects=projects, axis=axis)
    schema = build_initiatives_schema(
        [f"F{i}" for i in range(1, len(findings) + 1)],
        [f"PR{i}" for i in range(1, len(priorities) + 1)],
        [f"PJ{i}" for i in range(1, len(projects) + 1)], [c.key for c in criteria])
    llm, attempts, latency, error = call_model(provider, prompt, schema, lang=language)
    run_id = record_run(repo, provider, dossier_id=dossier_id, kind="initiatives", prompt=prompt,
                        status="ok" if llm else "invalid", attempts=attempts, latency_ms=latency,
                        output=llm.model_dump_json() if llm else "")
    repo.record_retrieval(run_id, passages)
    if llm is None:
        raise GenerationError(502, "MODEL_INVALID", f"Réponse du modèle invalide : {error}")

    plabel = {p.label: p.chunk.id for p in passages}
    flabel = {f"F{i}": f.id for i, f in enumerate(findings, 1)}
    prio_label = {f"PR{i}": p.id for i, p in enumerate(priorities, 1)}
    proj_label = {f"PJ{i}": p.id for i, p in enumerate(projects, 1)}
    valid_keys = {c.key for c in criteria}
    rejected: list[RejectedLink] = []

    def resolve(values: list[str], mapping: dict[str, str], kind: str, title: str) -> list[str]:
        """Seuls les identifiants réellement fournis passent ; les autres sont rejetés et signalés."""
        out = []
        for v in values:
            if _lbl(v) in mapping:
                out.append(mapping[_lbl(v)])
            else:
                rejected.append(RejectedLink(initiative=title, kind=kind, value=v))
        return list(dict.fromkeys(out))

    drafts: list[tuple[Initiative, list[str]]] = []
    fmap = {f.id: f for f in findings}
    for li in llm.initiatives:
        if _echo(li.title):  # le modèle a recopié la consigne au lieu d'un titre (vu en réel) : écarté, signalé
            rejected.append(RejectedLink(initiative=li.title[:80], kind="bad_title", value=li.title[:80]))
            continue
        fids = resolve(li.findings, flabel, "finding", li.title)
        if not fids:  # une initiative sans constat n'a pas de preuve : écartée et signalée
            rejected.append(RejectedLink(initiative=li.title, kind="no_finding", value=li.title))
            continue
        scores = {}
        for sc in li.scores:
            if sc.key in valid_keys:
                scores[sc.key] = CriterionScore(
                    key=sc.key, value=sc.value, rationale=sc.rationale,
                    source_ids=[plabel[_lbl(x)] for x in sc.sources if _lbl(x) in plabel])
        known = [fmap[i].text for i in fids] + [chunks[c].text for i in fids for c in
                                               fmap[i].source_ids if c in chunks]
        known += [p.title + " " + p.description for p in priorities] + [p.title for p in projects]
        flags = proposals.unsourced_numbers(
            f"{li.objective} {li.expected_result} {li.indicator}", known)
        drafts.append((Initiative(
            id=new_id("ini"), title=li.title, description=li.description, finding_ids=fids,
            proposal_flags=flags, scores=list(scores.values()), objective=li.objective,
            expected_result=li.expected_result, indicator=li.indicator, axis=axis,
            priority_ids=resolve(li.priorities, prio_label, "priority", li.title),
            depends_on_projects=resolve(li.depends_on_projects, proj_label, "project", li.title)),
            li.depends_on_titles))
    return drafts, rejected, not_sent, run_id

def coherence_of(repo, dossier_id: str, road: RoadmapResult) -> coh.CoherenceReport:
    """Contrôles 1 à 8 sur l'état ACTUEL des constats validés, priorités et projets du dossier."""
    return coh.check(road.items, repo.list_findings(dossier_id, validated_only=True),
                     repo.list_priorities(dossier_id), repo.list_projects(dossier_id))


def coherence(repo, deliverable_id: str) -> dict:
    row = get_deliverable(repo, deliverable_id)
    if row is None or row["type"] != "roadmap":
        raise GenerationError(404, "NOT_FOUND", "Feuille de route introuvable")
    _, content = repo.get_version(deliverable_id)
    if content.roadmap is None:
        raise GenerationError(404, "NOT_FOUND", "Feuille de route vide")
    return coherence_of(repo, row["dossier_id"], content.roadmap).model_dump(mode="json")


def patch(repo, deliverable_id: str, user: CurrentUser, changes: list[dict], *,
          waves: int | None = None) -> dict:
    """Modifie scores, durées, dépendances d'initiatives puis recalcule (sans modèle)."""
    row = get_deliverable(repo, deliverable_id)
    if row is None or row["type"] != "roadmap":
        raise GenerationError(404, "NOT_FOUND", "Feuille de route introuvable")
    if row["state"] != "draft":
        raise GenerationError(409, "NOT_DRAFT", "Le livrable n'est plus en brouillon")
    _, content = repo.get_version(deliverable_id)
    road = content.roadmap
    inis = {it.initiative.id: it.initiative for it in road.items}
    keys = {c.key for c in road.criteria}
    for ch in changes:
        iid = ch["id"]
        if iid not in inis:
            raise GenerationError(422, "UNKNOWN_INITIATIVE", f"Initiative inconnue : {iid}")
        ini = inis[iid]
        upd: dict = {}
        if ch.get("scores") is not None:
            cur = {sc.key: sc for sc in ini.scores}
            for sc in ch["scores"]:
                if sc["key"] not in keys:
                    raise GenerationError(422, "UNKNOWN_CRITERION", f"Critère inconnu : {sc['key']}")
                old = cur.get(sc["key"])
                cur[sc["key"]] = CriterionScore(
                    key=sc["key"], value=sc["value"],
                    source_ids=old.source_ids if old else [],
                    rationale=sc.get("rationale") or (old.rationale if old else "Saisi par le consultant"))
            upd["scores"] = list(cur.values())
        if "duration_weeks" in ch:
            upd["duration_weeks"] = ch["duration_weeks"]
        for fld in ("objective", "expected_result", "indicator"):
            if ch.get(fld) is not None:
                upd[fld] = ch[fld]
                upd["proposal_status"] = "accepted"  # un humain a écrit ou corrigé le texte
        if ch.get("accept_proposal") is not None:
            upd["proposal_status"] = "accepted" if ch["accept_proposal"] else "proposed"
        if ch.get("priority_ids") is not None:
            known = {p.id: p for p in repo.list_priorities(row["dossier_id"])}
            for pid in ch["priority_ids"]:
                if pid not in known:
                    raise GenerationError(422, "BAD_PRIORITY", f"Priorité inconnue : {pid}")
                if known[pid].status != "validated" and pid not in ini.priority_ids:
                    raise GenerationError(422, "PRIORITY_NOT_VALIDATED",
                                          f"Priorité non validée : {known[pid].title}")
            upd["priority_ids"] = list(dict.fromkeys(ch["priority_ids"]))
        if ch.get("depends_on_projects") is not None:
            known = {p.id for p in repo.list_projects(row["dossier_id"])}
            for pid in ch["depends_on_projects"]:
                if pid not in known:
                    raise GenerationError(422, "BAD_PROJECT", f"Projet inconnu : {pid}")
            upd["depends_on_projects"] = list(dict.fromkeys(ch["depends_on_projects"]))
        if ch.get("depends_on") is not None:
            for d in ch["depends_on"]:
                if d not in inis or d == iid:
                    raise GenerationError(422, "BAD_DEPENDENCY", f"Dépendance invalide : {d}")
            upd["depends_on"] = list(dict.fromkeys(ch["depends_on"]))
        inis[iid] = ini.model_copy(update=upd)
    old_waves = max((it.wave for it in road.items), default=3)
    result, warnings = compute(list(inis.values()), road.criteria, waves or old_waves,
                               repo.list_findings(row["dossier_id"], validated_only=True),
                               repo.list_priorities(row["dossier_id"]))
    result = result.model_copy(update={"rejected_links": road.rejected_links,
                                       "passages_not_sent": road.passages_not_sent})
    version = repo.add_version(deliverable_id, content.model_copy(update={"roadmap": result}),
                               user.id, "edited")
    repo.audit(user.id, "roadmap.update", "deliverable", deliverable_id,
               {"version": version, "initiatives": [c["id"] for c in changes]})
    return {"version": version, "warnings": warnings, "roadmap": result.model_dump(mode="json"),
            "coherence": coherence_of(repo, row["dossier_id"], result).model_dump(mode="json")}


def _from_recommendations(repo, provider, dossier_id, user, findings, criteria, waves, priorities, language):
    """Mode « recommandations » : axes = recommandations, initiatives = sous-points, vague = échéance.
    Rend None s'il n'y a aucune recommandation retenue (on passe alors au regroupement par le sens)."""
    from sqlalchemy import select

    from ..storage import schema as sch
    from . import jobs, roadmap_recos
    from .reco_details import dossier_links
    rc = sch.audit_recommendations.c
    with repo.engine.connect() as c:
        recs = [dict(r._mapping) for r in c.execute(select(sch.audit_recommendations).where(
            rc.dossier_id == dossier_id, rc.status.in_(("proposed", "validated"))))]
    if not recs:
        return None
    job = jobs.current()
    job.step(f"{len(recs)} recommandation(s) retenue(s) : chacune devient un axe, ses sous-points des initiatives")
    links, rows = dossier_links(repo, dossier_id)
    problems = [f for f in findings if (rows.get(f.id) and rows[f.id].kind) != "positif"]
    job.step(f"{len(problems)} constat(s) validé(s) à répartir (les points positifs ne justifient pas d'action)")
    initiatives, warns, stats = roadmap_recos.build(recs, problems, links, provider)
    job.step(f"{len(initiatives)} initiative(s) ; vagues fixées par les échéances du rapport, sinon la gravité")
    result, warnings = compute(initiatives, criteria, waves, problems, priorities)
    by_id = {i.id: i for i in initiatives}
    items = [it.model_copy(update={"wave": (by_id[it.initiative.id].recommendation or {}).get("wave", it.wave)})
             for it in result.items]
    items.sort(key=lambda it: (it.wave, it.rank))
    result = result.model_copy(update={"items": items})
    template = load_template("roadmap", language)
    did = repo.create_deliverable(dossier_id, "roadmap", template.id, user.id)
    version = repo.add_version(did, DeliverableContent(
        type="roadmap", language=language, template_id=template.id,
        template_version=template.version, sections=[], roadmap=result), user.id, "generated")
    repo.audit(user.id, "roadmap.generate", "deliverable", did,
               {"mode": "recommendations", "initiatives": len(initiatives), "recommendations": len(recs),
                "orphans": len(stats.get("orphans", [])), "model_calls": 0})
    return {"deliverable_id": did, "version": version, "mode": "recommendations",
            "warnings": [w for w in warnings if "vague" not in w.lower()] + warns,
            "roadmap": result.model_dump(mode="json"),
            "coherence": coherence_of(repo, dossier_id, result).model_dump(mode="json")}
