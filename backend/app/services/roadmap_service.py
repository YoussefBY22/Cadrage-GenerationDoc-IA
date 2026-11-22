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
from app.generation.llm_schemas import LLMInitiatives
from app.generation.prompting import (
    build_initiatives_prompt,
    fit_passages,
    passage_budget,
    safe_tokens,
    system_prompt,
)
from app.generation.template_loader import load_template
from app.llm.base import LLMProvider
from app.roadmap import coherence as coh
from app.roadmap import graph, scoring

from .generation import GenerationError, call_model, get_deliverable, new_nonce, record_run

MAX_PASSAGES = 30
ROADMAP_REPLY_TOKENS = 1200


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


def generate(repo, provider: LLMProvider, dossier_id: str, user: CurrentUser, *,
             criteria: list[Criterion] | None = None, waves: int = 3,
             language: str = "fr") -> dict:
    findings = repo.list_findings(dossier_id, validated_only=True)
    if not findings:
        raise GenerationError(409, "NO_VALIDATED_FINDINGS",
                              "Validez d'abord des constats avant de générer la feuille de route")
    criteria = criteria or scoring.DEFAULT_CRITERIA
    priorities = repo.list_priorities(dossier_id, "validated")  # seules les validées servent
    projects = repo.list_projects(dossier_id)
    all_ids = list(dict.fromkeys(i for f in findings for i in f.source_ids))
    ids = all_ids[:MAX_PASSAGES]
    chunks = repo.get_chunks(dossier_id, ids)
    passages = [Passage(label=f"P{n}", chunk=chunks[i], score=0.0, ranks={})
                for n, i in enumerate((i for i in ids if i in chunks), 1)]
    nonce = new_nonce()
    fixed = system_prompt(language) + build_initiatives_prompt(
        findings, [], criteria, nonce=nonce, lang=language, priorities=priorities,
        projects=projects)
    ctx_tokens = getattr(provider, "context_tokens", None)
    if ctx_tokens and safe_tokens(fixed) + ROADMAP_REPLY_TOKENS + 64 > ctx_tokens:
        raise GenerationError(
            409, "CONTEXT_FULL",
            f"Constats, priorités et projets (~{safe_tokens(fixed)} jetons) ne tiennent pas dans la "
            f"fenêtre du modèle ({ctx_tokens}) : réduisez-les ou choisissez un modèle à plus grande "
            "fenêtre. Rien n'a été coupé.")
    budget = passage_budget(ctx_tokens, fixed, ROADMAP_REPLY_TOKENS)
    passages = fit_passages(passages, nonce, budget)  # seuls les passages lus sont citables
    not_sent = len(all_ids) - len(passages)  # coupe par le plafond ou la fenêtre : jamais silencieuse
    prompt = build_initiatives_prompt(findings, passages, criteria, nonce=nonce, budget=budget,
                                      lang=language, priorities=priorities, projects=projects)
    llm, attempts, latency, error = call_model(provider, prompt, LLMInitiatives, lang=language)
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
        drafts.append((Initiative(
            id=new_id("ini"), title=li.title, description=li.description, finding_ids=fids,
            scores=list(scores.values()), objective=li.objective,
            expected_result=li.expected_result, indicator=li.indicator,
            priority_ids=resolve(li.priorities, prio_label, "priority", li.title),
            depends_on_projects=resolve(li.depends_on_projects, proj_label, "project", li.title)),
            li.depends_on_titles))
    by_title = {_title_key(i.title): i.id for i, _ in drafts}
    initiatives = []
    for ini, deps in drafts:
        dep_ids = []
        for t_ in deps:
            hit = by_title.get(_title_key(t_))
            if hit is None:
                rejected.append(RejectedLink(initiative=ini.title, kind="initiative", value=t_))
            elif hit != ini.id:
                dep_ids.append(hit)
        initiatives.append(ini.model_copy(update={"depends_on": list(dict.fromkeys(dep_ids))}))
    result, warnings = compute(initiatives, criteria, waves, findings, priorities)
    result = result.model_copy(update={"rejected_links": rejected, "passages_not_sent": not_sent})

    template = load_template("roadmap", language)
    did = repo.create_deliverable(dossier_id, "roadmap", template.id, user.id)
    version = repo.add_version(did, DeliverableContent(
        type="roadmap", language=language, template_id=template.id,
        template_version=template.version, sections=[], roadmap=result), user.id, "generated")
    repo.audit(user.id, "roadmap.generate", "deliverable", did,
               {"initiatives": len(initiatives), "run_id": run_id, "model": provider.name,
                "rejected_links": len(rejected), "passages_not_sent": not_sent,
                "priorities": len(priorities), "projects": len(projects)})
    return {"deliverable_id": did, "version": version, "warnings": warnings,
            "roadmap": result.model_dump(mode="json"),
            "coherence": coherence_of(repo, dossier_id, result).model_dump(mode="json")}


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
        if ch.get("priority_ids") is not None:
            known = {p.id for p in repo.list_priorities(row["dossier_id"])}
            for pid in ch["priority_ids"]:
                if pid not in known:
                    raise GenerationError(422, "BAD_PRIORITY", f"Priorité inconnue : {pid}")
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
