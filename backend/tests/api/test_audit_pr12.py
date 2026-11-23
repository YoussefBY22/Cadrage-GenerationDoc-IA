"""Corrections issues de l'audit réel de la PR 12 (points 1 à 8)."""

import pytest

from app.domain.roadmap import CriterionScore, Initiative
from app.domain.workflow import CurrentUser
from app.generation.llm_schemas import build_initiatives_schema
from app.llm import FakeProvider
from app.llm.base import LLMError
from app.roadmap import coherence as coh
from app.roadmap import proposals, scoring
from app.services import coeur
from app.services.generation import GenerationError
from tests.api.test_coeur import (
    DIAG,
    OTHER,
    TRAME,
    V1,
    make,  # noqa: F401  (fixture)
    mkprio,
    new_dossier,
    prepare,
    upload,
)
from tests.services.test_generation_fakes import _scores, honest

KEYS = [c.key for c in scoring.DEFAULT_CRITERIA]


# 1. schéma par appel, notes manquantes ---------------------------------------------------------
def test_1_schema_requires_fields_and_lists_provided_labels():
    s = build_initiatives_schema(["F1", "F2"], ["PR1"], [], KEYS).model_json_schema()
    ini = s["$defs"]["LLMInitiative"]
    assert set(ini["required"]) == set(ini["properties"])  # rien de facultatif pour le moteur
    assert ini["properties"]["priorities"]["items"]["enum"] == ["PR1"]
    assert ini["properties"]["findings"]["items"]["enum"] == ["F1", "F2"]
    assert ini["properties"]["depends_on_projects"]["maxItems"] == 0  # aucun projet fourni
    assert ini["properties"]["scores"]["minItems"] == len(KEYS)
    assert s["$defs"]["LLMScore"]["properties"]["key"]["enum"] == KEYS


def test_1_prompt_asks_to_examine_each_priority_and_schema_is_sent(make):  # noqa: F811
    seen = {}

    def handler(prompt, schema):
        if schema.__name__ == "LLMInitiatives":
            seen["schema"] = schema.model_json_schema()
            seen["prompt"] = prompt
        return honest(prompt, schema)

    c = make(FakeProvider(handler=handler))
    w = prepare(c)
    assert c.post(f"{V1}/dossiers/{w['did']}/roadmap:generate", json={}).status_code == 200
    ini = seen["schema"]["$defs"]["LLMInitiative"]
    assert ini["properties"]["priorities"]["items"]["enum"] == ["PR1"]
    assert ini["properties"]["depends_on_projects"]["items"]["enum"] == ["PJ1"]
    assert "CHAQUE priorité" in seen["prompt"]


def test_1_missing_score_is_not_evaluated_never_a_low_score(make):  # noqa: F811
    def handler(prompt, schema):
        if schema.__name__ != "LLMInitiatives":
            return honest(prompt, schema)
        return {"initiatives": [
            {"title": "Complète", "description": "d", "findings": ["F1"], "scores": _scores(3),
             "priorities": [], "depends_on_projects": [], "depends_on_titles": []},
            {"title": "Partielle", "description": "d", "findings": ["F1"],
             "scores": _scores(5)[:2], "priorities": [], "depends_on_projects": [],
             "depends_on_titles": []}]}

    c = make(FakeProvider(handler=handler))
    w = prepare(c, with_links=False)
    items = c.post(f"{V1}/dossiers/{w['did']}/roadmap:generate", json={}).json()["roadmap"]["items"]
    by = {i["initiative"]["title"]: i for i in items}
    assert by["Complète"]["unscored"] == [] and by["Complète"]["rank"] == 1
    assert by["Partielle"]["unscored"] == KEYS[2:] and by["Partielle"]["rank"] == 2


def test_1_unscored_ranks_after_scored_even_with_higher_partial_value():
    def ini(i, vals):
        return Initiative(id=i, title=i, description="", finding_ids=[],
                          scores=[CriterionScore(key=k, value=v, source_ids=[], rationale="")
                                  for k, v in zip(KEYS, vals, strict=False)])
    items = scoring.score([ini("a", [5, 5]), ini("b", [1, 1, 1, 5, 5])], scoring.DEFAULT_CRITERIA)
    assert [i.initiative.id for i in items] == ["b", "a"] and items[1].unscored


# 2. propositions IA -----------------------------------------------------------------------------
def test_2_numbers_absent_from_sources_are_flagged():
    src = ["Les agents saisissent 12 dossiers par jour."]
    assert proposals.unsourced_numbers("Former trois agents en quinze jours", src) == [
        "trois", "quinze"]
    assert proposals.unsourced_numbers("Traiter 12 dossiers", src) == []
    assert proposals.numbers_in("rester sous 2,5 jours") == ["2.5"]


def test_2_objective_result_indicator_are_proposals_until_a_human_accepts(make):  # noqa: F811
    def handler(prompt, schema):
        if schema.__name__ != "LLMInitiatives":
            return honest(prompt, schema)
        return {"initiatives": [{
            "title": "Automatiser", "description": "d", "findings": ["F1"], "scores": _scores(4),
            "priorities": [], "depends_on_projects": [], "depends_on_titles": [],
            "objective": "Former trois agents", "expected_result": "Moins de quinze jours",
            "indicator": "Taux d'erreur"}]}

    c = make(FakeProvider(handler=handler))
    w = prepare(c, with_links=False)
    body = c.post(f"{V1}/dossiers/{w['did']}/roadmap:generate", json={}).json()
    ini = body["roadmap"]["items"][0]["initiative"]
    assert ini["proposal_status"] == "proposed" and set(ini["proposal_flags"]) == {"trois", "quinze"}
    chain = body["coherence"]["chains"][0]
    assert chain["proposal_status"] == "proposed" and chain["proposal_flags"]
    dlv = body["deliverable_id"]
    r = c.patch(f"{V1}/deliverables/{dlv}/roadmap",
                json={"initiatives": [{"id": ini["id"], "accept_proposal": True}]}).json()
    assert r["roadmap"]["items"][0]["initiative"]["proposal_status"] == "accepted"
    r = c.patch(f"{V1}/deliverables/{dlv}/roadmap",
                json={"initiatives": [{"id": ini["id"], "accept_proposal": False}]}).json()
    assert r["roadmap"]["items"][0]["initiative"]["proposal_status"] == "proposed"
    r = c.patch(f"{V1}/deliverables/{dlv}/roadmap",
                json={"initiatives": [{"id": ini["id"], "objective": "Écrit par un humain"}]}).json()
    assert r["roadmap"]["items"][0]["initiative"]["proposal_status"] == "accepted"


# 3. priorités : création proposée, validation réservée ---------------------------------------
def test_3_create_is_always_proposed_and_patch_cannot_validate(make):  # noqa: F811
    c = make(FakeProvider(handler=honest))
    did = new_dossier(c)
    r = c.post(f"{V1}/dossiers/{did}/priorities", json={"title": "P", "status": "validated"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "CREATE_AS_PROPOSED"
    p = mkprio(c, did, "P")
    assert p["status"] == "proposed"
    r = c.patch(f"{V1}/priorities/{p['id']}", json={"status": "validated"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "VALIDATION_RESERVED"
    r = c.patch(f"{V1}/priorities/{p['id']}", json={"title": "Q", "status": "validated"})
    assert r.status_code == 403


def test_3_only_reviewer_or_admin_decides_and_validator_is_recorded(repo):
    uid = repo.create_user("a@x.fr", "Camille Laurent", "h", "consultant")
    did = repo.create_dossier("D", "C", "fr", uid)
    p = repo.create_priority(did, title="P", description="", rank=1, status="proposed",
                             source_ids=[], author_id=uid)
    with pytest.raises(GenerationError) as exc:
        coeur.decide(repo, p, CurrentUser(id=uid, role="consultant"), "validated")
    assert exc.value.status == 403
    rid = repo.create_user("r@x.fr", "Hugo Martin", "h", "reviewer")
    done = coeur.decide(repo, p, CurrentUser(id=rid, role="reviewer"), "validated")
    assert (done.status, done.validated_by) == ("validated", rid) and done.validated_at
    assert coeur.names(repo, [uid, rid]) == {uid: "Camille Laurent", rid: "Hugo Martin"}
    # relecteur du dossier sans rôle global
    other = repo.create_user("m@x.fr", "Membre", "h", "consultant")
    repo.add_member(did, other, "reviewer")
    assert coeur.can_validate(repo, did, CurrentUser(id=other, role="consultant"))


def test_3_edit_of_rank_title_or_description_requires_revalidation(make):  # noqa: F811
    c = make(FakeProvider(handler=honest))
    did = new_dossier(c)
    for change in ({"rank": 5}, {"title": "Autre"}, {"description": "Nouvelle"}):
        p = mkprio(c, did, "P", "validated")
        assert p["status"] == "validated"
        out = c.patch(f"{V1}/priorities/{p['id']}", json=change).json()
        assert out["status"] == "proposed" and out["validated_by"] is None
        assert out["validated_at"] is None


def test_3_initiative_patch_refuses_unvalidated_priority(make):  # noqa: F811
    c = make(FakeProvider(handler=honest))
    w = prepare(c, with_links=False)
    body = c.post(f"{V1}/dossiers/{w['did']}/roadmap:generate", json={}).json()
    pending = mkprio(c, w["did"], "Pas encore validée")
    ini = body["roadmap"]["items"][0]["initiative"]["id"]
    r = c.patch(f"{V1}/deliverables/{body['deliverable_id']}/roadmap",
                json={"initiatives": [{"id": ini, "priority_ids": [pending["id"]]}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "PRIORITY_NOT_VALIDATED"


# 4. aucune date inventée -----------------------------------------------------------------------
def _scored(ini, rank=1, wave=1):
    from app.domain.roadmap import ScoredInitiative
    return ScoredInitiative(initiative=ini, score=0.5, rank=rank, wave=wave)


def _ini(i, deps=(), pdeps=(), dur=3):
    return Initiative(id=i, title=i, description="", finding_ids=[], scores=[],
                      depends_on=list(deps), depends_on_projects=list(pdeps), duration_weeks=dur)


def _proj(i, state, dur=None):
    from app.domain.coeur import ExistingProject
    return ExistingProject(id=i, dossier_id="d", title=i, state=state, duration_weeks=dur)


def test_4_project_dependency_without_done_gives_order_only():
    items = [_scored(_ini("a", pdeps=("p1",)))]
    seq = coh.build_sequence(items, [_proj("p1", "in_progress")])
    assert (seq[0].start_week, seq[0].end_week) == (None, None)
    seq = coh.build_sequence(items, [_proj("p1", "planned", dur=8)])  # même avec une durée
    assert seq[0].end_week is None
    seq = coh.build_sequence(items, [_proj("p1", "done")])
    assert (seq[0].start_week, seq[0].end_week) == (0, 3)


def test_4_gantt_has_no_default_duration_and_no_critical_path_without_durations():
    from app.export.pptx_export import gantt_schedule
    from app.roadmap.graph import analyze
    items = [_scored(_ini("a", dur=None)), _scored(_ini("b", dur=2), 2)]
    assert gantt_schedule(items) is None
    assert analyze([x.initiative for x in items])[2] == []
    full = [_scored(_ini("a", dur=1)), _scored(_ini("b", dur=2), 2)]
    assert gantt_schedule(full) is not None


# 5. vagues --------------------------------------------------------------------------------------
def test_5_waves_start_at_one():
    def ini(i, v):
        return Initiative(id=i, title=i, description="", finding_ids=[],
                          scores=[CriterionScore(key=k, value=v, source_ids=[], rationale="")
                                  for k in KEYS])
    two = scoring.score([ini("a", 5), ini("b", 2)], scoring.DEFAULT_CRITERIA, waves=3)
    assert [i.wave for i in two] == [1, 2]
    assert [i.wave for i in scoring.score([ini("a", 5)], scoring.DEFAULT_CRITERIA, waves=3)] == [1]
    four = scoring.score([ini(x, v) for x, v in zip("abcd", (5, 4, 3, 2), strict=True)],
                         scoring.DEFAULT_CRITERIA, waves=3)
    assert [i.wave for i in four] == [1, 2, 3, 3]


# 6. couverture ---------------------------------------------------------------------------------
def test_6_failed_batches_are_not_counted_as_read(make):  # noqa: F811
    def handler(prompt, schema):
        if schema.__name__ == "LLMFindings":
            raise LLMError("JSON invalide")
        return honest(prompt, schema)

    c = make(FakeProvider(handler=handler))
    did = new_dossier(c)
    upload(c, did, "a.txt", DIAG, "diagnostic")
    upload(c, did, "s.txt", OTHER, "strategy")
    upload(c, did, "t.txt", TRAME, "template")
    cov = c.post(f"{V1}/dossiers/{did}/findings:extract").json()["coverage"]
    assert (cov["chunks_read"], cov["chunks_failed"], cov["chunks_total"]) == (0, 1, 1)
    assert {(e["filename"], e["role"]) for e in cov["excluded"]} == {
        ("s.txt", "strategy"), ("t.txt", "template")}
    assert all(e["reason"] for e in cov["excluded"])


# 7. doublon ------------------------------------------------------------------------------------
@pytest.mark.parametrize("a,b", [
    ("Audit de la sécurité du système d'information", "Système information"),
    ("Formation agents", "Délais paiement"),
    ("Délais paiement", "Formation agents"),
])
def test_7_no_false_duplicate(a, b):
    assert coh.similarity(a, b) < coh.DUPLICATE_THRESHOLD


def test_7_real_duplicate_still_detected():
    assert coh.similarity("Migration de la messagerie vers le nuage",
                          "Migration messagerie vers nuage") >= coh.DUPLICATE_THRESHOLD


# 8. une trame n'est jamais citable -----------------------------------------------------------------
def test_8_template_excluded_even_with_explicit_ids_or_only_templates(make):  # noqa: F811
    c = make(FakeProvider(handler=honest))
    did = new_dossier(c)
    t = upload(c, did, "t.txt", TRAME, "template")["document_id"]
    search = {"texts": ["plan type du rapport"], "k": 5}
    assert c.post(f"{V1}/dossiers/{did}/search", json=search).json() == []  # que des trames
    assert c.post(f"{V1}/dossiers/{did}/search", json={**search, "document_ids": [t]}).json() == []
    b = upload(c, did, "b.txt", OTHER)["document_id"]
    hits = c.post(f"{V1}/dossiers/{did}/search", json={**search, "document_ids": [t, b]}).json()
    assert all(h["chunk"]["document_id"] == b for h in hits)
    # une priorité ne peut pas citer une trame
    tchunk = next(iter(c.app.state.repo.iter_chunks(did, [t]))).id
    r = c.post(f"{V1}/dossiers/{did}/priorities", json={"title": "X", "source_ids": [tchunk]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "TEMPLATE_SOURCE"


# --- écarts mineurs (2e audit) ---------------------------------------------------------------
def test_m1_initiative_containing_all_words_of_a_short_project_is_not_a_duplicate():
    assert coh.similarity("Recruter des agents de formation", "Formation agents") < \
        coh.DUPLICATE_THRESHOLD
    assert coh.similarity("Migration de la messagerie vers le nuage",
                          "Migration messagerie vers nuage") >= coh.DUPLICATE_THRESHOLD


def test_m2_reviewer_cannot_validate_their_own_priority_admin_can(repo):
    rid = repo.create_user("r@x.fr", "Hugo", "h", "reviewer")
    admin = repo.create_user("a@x.fr", "Root", "h", "admin")
    did = repo.create_dossier("D", "C", "fr", rid)
    p = repo.create_priority(did, title="P", description="", rank=1, status="proposed",
                             source_ids=[], author_id=rid)
    with pytest.raises(GenerationError) as exc:
        coeur.decide(repo, p, CurrentUser(id=rid, role="reviewer"), "validated")
    assert exc.value.status == 403 and exc.value.code == "SELF_VALIDATION"
    other = repo.create_user("r2@x.fr", "Autre", "h", "reviewer")
    assert coeur.decide(repo, p, CurrentUser(id=other, role="reviewer"), "validated").status \
        == "validated"
    q = repo.create_priority(did, title="Q", description="", rank=2, status="proposed",
                             source_ids=[], author_id=admin)
    assert coeur.decide(repo, q, CurrentUser(id=admin, role="admin"), "validated").status \
        == "validated"


def test_m3_numbers_are_compared_by_value_digits_or_words():
    f = proposals.unsourced_numbers
    assert f("Former deux agents", ["Il y a 2 agents."]) == []
    assert f("Former 2 agents", ["Il y a deux agents."]) == []
    assert f("Atteindre vingt jours", ["Délai de 20 jours."]) == []
    assert f("Atteindre 30 jours", ["Délai de trente jours."]) == []
    assert f("Atteindre quinze jours", ["Délai de 15 jours."]) == []
    assert f("Atteindre 12 jours", ["Délai de douze jours."]) == []
    assert f("Former trois agents", ["Il y a 2 agents."]) == ["trois"]
    assert f("Former 3 agents", ["Il y a deux agents."]) == ["3"]
