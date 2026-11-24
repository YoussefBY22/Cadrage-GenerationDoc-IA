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
from app.generation.llm_schemas import build_axes_schema, build_initiatives_schema
from app.generation.prompting import (
    build_axes_prompt,
    build_initiatives_prompt,
    fit_passages,
    passage_budget,
    render_axis_findings,
    safe_tokens,
    system_prompt,
)
from app.generation.template_loader import load_template
from app.llm.base import LLMProvider
from app.roadmap import axes as axes_mod
from app.roadmap import coherence as coh
from app.roadmap import graph, proposals, scoring

from .generation import GenerationError, call_model, get_deliverable, new_nonce, record_run

MAX_PASSAGES = 30
ROADMAP_REPLY_TOKENS = 1200
AXES_REPLY_TOKENS = 500
AXES_BATCH = 25  # constats par appel « axes » (réponse courte)
MAX_FINDINGS_PER_CALL = 8  # réponse courte : quelques initiatives par appel, jamais tronquée
SMALL_ROADMAP = 8  # jusqu'à 8 constats distincts : un seul appel, sans étape « axes »


def _lbl(x: str) -> str:
    return re.sub(r"\W", "", x).upper()


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


def _find_axes(repo, provider, dossier_id, reps, language, ctx_tokens) -> tuple[list, list[str], int]:
    """Étape 1 : le modèle range les constats en axes, par lots qui tiennent ; les axes créés sont rappelés."""
    book = axes_mod.AxisBook()
    nonce = new_nonce()
    fixed = system_prompt(language) + build_axes_prompt([], ["x" * 40] * 7, nonce=nonce, lang=language)
    room = (ctx_tokens or 4096) - safe_tokens(fixed) - AXES_REPLY_TOKENS - 64

    def cost(f):
        return safe_tokens(render_axis_findings([f], nonce)) + 1

    lots = [b[i:i + AXES_BATCH] for b in axes_mod.batches(reps, cost, max(room, 200))
            for i in range(0, len(b), AXES_BATCH)]
    calls = 0
    failed: list[str] = []
    for lot in lots:
        prompt = build_axes_prompt(lot, book.names, nonce=nonce, lang=language)
        labels = [f"F{i}" for i in range(1, len(lot) + 1)]
        llm, attempts, latency, error = call_model(provider, prompt, build_axes_schema(labels),
                                                   lang=language)
        calls += 1
        record_run(repo, provider, dossier_id=dossier_id, kind="axes", prompt=prompt,
                   status="ok" if llm else "invalid", attempts=attempts, latency_ms=latency,
                   output=llm.model_dump_json() if llm else "")
        if llm is None:
            failed.append(error or "")
            continue
        for row in llm.assignments:
            num = _lbl(row.finding)[1:]
            k = int(num) if num.isdigit() else 0
            if 1 <= k <= len(lot):
                book.assign(lot[k - 1].id, row.axis)
    return book.groups(reps), failed, calls


def generate(repo, provider: LLMProvider, dossier_id: str, user: CurrentUser, *,
             criteria: list[Criterion] | None = None, waves: int = 3,
             language: str = "fr") -> dict:
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
    ctx_tokens = getattr(provider, "context_tokens", None)
    nonce = new_nonce()

    reps, dups = axes_mod.dedupe(findings)
    fixed1 = _fixed_prompt(reps[:1], criteria, priorities, projects, nonce, language, "x" * 40)
    if ctx_tokens and safe_tokens(fixed1) + ROADMAP_REPLY_TOKENS + 64 > ctx_tokens:
        raise GenerationError(
            409, "CONTEXT_FULL",
            f"Priorités et projets (~{safe_tokens(fixed1)} jetons) ne tiennent pas dans la "
            f"fenêtre du modèle ({ctx_tokens}), même avec un seul constat : réduisez-les ou choisissez un "
            "modèle à plus grande fenêtre. Rien n'a été coupé.")
    direct = len(reps) <= SMALL_ROADMAP and _fits(ctx_tokens, reps, criteria, priorities, projects,
                                                  nonce, language, None)
    axis_errors: list[str] = []
    axis_calls = 0
    if direct:
        groups: list[tuple[str | None, list]] = [(None, reps)]
    else:
        groups, axis_errors, axis_calls = _find_axes(repo, provider, dossier_id, reps, language,
                                                    ctx_tokens)

    rejected: list[RejectedLink] = []
    not_sent = 0
    run_ids: list[str] = []
    part_errors: list[str] = []
    failed_findings: list[str] = []
    drafts: list[tuple[Initiative, list[str]]] = []
    fmap = {f.id: f for f in findings}
    for axis, group in groups:
        def fits(part, axis=axis):
            return _fits(ctx_tokens, part, criteria, priorities, projects, nonce, language, axis)

        for part in _split_to_fit(group, fits):
            try:
                d, rj, ns, rid = _propose(repo, provider, dossier_id, part, criteria, priorities,
                                          projects, language, axis, ctx_tokens)
            except GenerationError as exc:  # une partie ratée n'efface pas les autres : signalée
                part_errors.append(f"{axis or '-'} : {exc.message}"[:300])
                failed_findings += [f.id for f in part]
                continue
            drafts += d
            rejected += rj
            not_sent += ns
            run_ids.append(rid)

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
                "axis_errors": len(axis_errors), "part_errors": part_errors})
    return {"deliverable_id": did, "version": version, "warnings": warnings + [f"Partie non générée, constats à reprendre : {e}" for e in part_errors] + [f"Rangement en axes incomplet : {e}" for e in axis_errors],
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
