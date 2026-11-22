"""Feuille de route : constats validés → initiatives notées → priorité, vagues, chemin critique."""

import re

from app.domain.generation import DeliverableContent
from app.domain.ids import new_id
from app.domain.retrieval import Passage
from app.domain.roadmap import Criterion, CriterionScore, Initiative, RoadmapResult
from app.domain.workflow import CurrentUser
from app.generation.llm_schemas import LLMInitiatives
from app.generation.prompting import build_initiatives_prompt
from app.generation.template_loader import load_template
from app.llm.base import LLMProvider
from app.roadmap import graph, scoring
from app.roadmap.referentiels import normalize_domain

from .generation import GenerationError, call_model, get_deliverable, new_nonce, record_run

MAX_PASSAGES = 30


def _lbl(x: str) -> str:
    return re.sub(r"\W", "", x).upper()


def _title_key(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())


def compute(initiatives: list[Initiative], criteria: list[Criterion], waves: int
            ) -> tuple[RoadmapResult, list[str]]:
    """Calcul déterministe, sans modèle : score, rang, vagues, ordre topologique, cycles."""
    items, warnings = scoring.score_with_warnings(initiatives, criteria, waves)
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
    ids = list(dict.fromkeys(i for f in findings for i in f.source_ids))[:MAX_PASSAGES]
    chunks = repo.get_chunks(dossier_id, ids)
    passages = [Passage(label=f"P{n}", chunk=chunks[i], score=0.0, ranks={})
                for n, i in enumerate((i for i in ids if i in chunks), 1)]
    prompt = build_initiatives_prompt(findings, passages, criteria, nonce=new_nonce(),
                                      lang=language)
    llm, attempts, latency, error = call_model(provider, prompt, LLMInitiatives, lang=language)
    run_id = record_run(repo, provider, dossier_id=dossier_id, kind="initiatives", prompt=prompt,
                        status="ok" if llm else "invalid", attempts=attempts, latency_ms=latency,
                        output=llm.model_dump_json() if llm else "")
    repo.record_retrieval(run_id, passages)
    if llm is None:
        raise GenerationError(502, "MODEL_INVALID", f"Réponse du modèle invalide : {error}")

    plabel = {p.label: p.chunk.id for p in passages}
    flabel = {f"F{i}": f.id for i, f in enumerate(findings, 1)}
    valid_keys = {c.key for c in criteria}
    drafts: list[tuple[Initiative, list[str]]] = []
    for li in llm.initiatives:
        fids = list(dict.fromkeys(flabel[_lbl(x)] for x in li.findings if _lbl(x) in flabel))
        if not fids:  # une initiative sans constat n'a pas de preuve : écartée
            continue
        scores = {}
        for sc in li.scores:
            if sc.key in valid_keys:
                scores[sc.key] = CriterionScore(
                    key=sc.key, value=sc.value, rationale=sc.rationale,
                    source_ids=[plabel[_lbl(x)] for x in sc.sources if _lbl(x) in plabel])
        drafts.append((Initiative(id=new_id("ini"), title=li.title, description=li.description,
                                  finding_ids=fids, scores=list(scores.values()),
                                  domain=normalize_domain(li.domain)),
                       li.depends_on_titles))
    by_title = {_title_key(i.title): i.id for i, _ in drafts}
    initiatives = []
    for ini, deps in drafts:
        dep_ids = [by_title[_title_key(t)] for t in deps
                   if _title_key(t) in by_title and by_title[_title_key(t)] != ini.id]
        initiatives.append(ini.model_copy(update={"depends_on": list(dict.fromkeys(dep_ids))}))
    result, warnings = compute(initiatives, criteria, waves)

    template = load_template("roadmap", language)
    did = repo.create_deliverable(dossier_id, "roadmap", template.id, user.id)
    version = repo.add_version(did, DeliverableContent(
        type="roadmap", language=language, template_id=template.id,
        template_version=template.version, sections=[], roadmap=result), user.id, "generated")
    repo.audit(user.id, "roadmap.generate", "deliverable", did,
               {"initiatives": len(initiatives), "run_id": run_id, "model": provider.name})
    return {"deliverable_id": did, "version": version, "warnings": warnings,
            "roadmap": result.model_dump(mode="json")}


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
        if ch.get("depends_on") is not None:
            for d in ch["depends_on"]:
                if d not in inis or d == iid:
                    raise GenerationError(422, "BAD_DEPENDENCY", f"Dépendance invalide : {d}")
            upd["depends_on"] = list(dict.fromkeys(ch["depends_on"]))
        inis[iid] = ini.model_copy(update=upd)
    old_waves = max((it.wave for it in road.items), default=3)
    result, warnings = compute(list(inis.values()), road.criteria, waves or old_waves)
    version = repo.add_version(deliverable_id, content.model_copy(update={"roadmap": result}),
                               user.id, "edited")
    repo.audit(user.id, "roadmap.update", "deliverable", deliverable_id,
               {"version": version, "initiatives": [c["id"] for c in changes]})
    return {"version": version, "warnings": warnings, "roadmap": result.model_dump(mode="json")}
