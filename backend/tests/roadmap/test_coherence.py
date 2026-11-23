"""Contrôles 1 à 8 de docs/15 §3 : pour chacun, un cas qui le déclenche et un cas qui ne le déclenche pas."""

from app.domain.coeur import ExistingProject, Priority
from app.domain.generation import Finding
from app.domain.roadmap import CriterionScore, Initiative, ScoredInitiative
from app.roadmap import coherence as coh
from app.roadmap import scoring


def F(i, severity="high", sources=("c1",)):
    return Finding(id=i, dossier_id="d", text=f"constat {i}", theme="t", severity=severity,
                   source_ids=list(sources), validated=True)


def P(i, rank=1, status="validated", sources=()):
    return Priority(id=i, dossier_id="d", title=f"priorité {i}", rank=rank, status=status,
                    source_ids=list(sources))


def PJ(i, title, state="in_progress"):
    return ExistingProject(id=i, dossier_id="d", title=title, state=state, source_ids=["c9"])


def I(i, title=None, findings=("f1",), priorities=("p1",), deps=(), pdeps=(), duration=1, **kw):
    return Initiative(id=i, title=title or f"initiative {i}", description="", finding_ids=list(findings),
                      scores=[], depends_on=list(deps), duration_weeks=duration,
                      priority_ids=list(priorities), depends_on_projects=list(pdeps), **kw)


def S(ini, rank=1, wave=1, score=0.5):
    return ScoredInitiative(initiative=ini, score=score, rank=rank, wave=wave)


def run(items, findings=(), priorities=(), projects=()):
    return coh.check(list(items), list(findings), list(priorities), list(projects))


def of(report, code):
    return [i for i in report.issues if i.code == code]


# 1 -------------------------------------------------------------------------------------------
def test_1_major_finding_without_initiative():
    r = run([S(I("a"))], [F("f1"), F("f2", "high")], [P("p1")])
    assert [i.refs["finding_id"] for i in of(r, coh.FINDING_NO_INITIATIVE)] == ["f2"]


def test_1_minor_or_covered_findings_are_fine():
    r = run([S(I("a"))], [F("f1"), F("f3", "low")], [P("p1")])
    assert not of(r, coh.FINDING_NO_INITIATIVE)


# 2 -------------------------------------------------------------------------------------------
def test_2_initiative_without_finding_or_priority():
    r = run([S(I("a", findings=(), priorities=()))], [F("f1")], [P("p1")])
    (issue,) = of(r, coh.INITIATIVE_UNANCHORED)
    assert issue.refs["missing"] == ["finding", "priority"]


def test_2_only_validated_priorities_count():
    r = run([S(I("a"))], [F("f1")], [P("p1", status="proposed")])
    assert of(r, coh.INITIATIVE_UNANCHORED)[0].refs["missing"] == ["priority"]


def test_2_anchored_initiative_is_fine():
    assert not of(run([S(I("a"))], [F("f1")], [P("p1")]), coh.INITIATIVE_UNANCHORED)


# 3 -------------------------------------------------------------------------------------------
def test_3_validated_priority_without_initiative():
    r = run([S(I("a"))], [F("f1")], [P("p1"), P("p2", rank=2)])
    assert [i.refs["priority_id"] for i in of(r, coh.PRIORITY_NO_INITIATIVE)] == ["p2"]


def test_3_rejected_or_used_priorities_are_fine():
    r = run([S(I("a"))], [F("f1")], [P("p1"), P("p2", status="rejected")])
    assert not of(r, coh.PRIORITY_NO_INITIATIVE)


# 4 -------------------------------------------------------------------------------------------
def test_4_duplicate_of_project_in_progress():
    r = run([S(I("a", title="Migration de la messagerie vers le nuage"))], [F("f1")], [P("p1")],
            [PJ("j1", "Migration messagerie vers nuage")])
    (issue,) = of(r, coh.INITIATIVE_DUPLICATES_PROJECT)
    assert issue.refs["project_id"] == "j1"


def test_4_done_project_unrelated_or_declared_dependency_is_fine():
    ini = I("a", title="Migration de la messagerie vers le nuage")
    done = PJ("j1", "Migration messagerie vers nuage", state="done")
    other = PJ("j2", "Refonte du site web public")
    assert not of(run([S(ini)], [F("f1")], [P("p1")], [done, other]),
                  coh.INITIATIVE_DUPLICATES_PROJECT)
    dep = I("a", title=ini.title, pdeps=("j1",))
    live = PJ("j1", "Migration messagerie vers nuage")
    assert not of(run([S(dep)], [F("f1")], [P("p1")], [live]), coh.INITIATIVE_DUPLICATES_PROJECT)


# 5 -------------------------------------------------------------------------------------------
def test_5_cycle():
    a, b = I("a", deps=("b",)), I("b", deps=("a",))
    r = run([S(a, 1), S(b, 2)], [F("f1")], [P("p1")])
    cyc = [i for i in of(r, coh.DEPENDENCY_ORDER) if i.refs["kind"] == "cycle"]
    assert cyc and cyc[0].severity == "blocking" and set(cyc[0].refs["initiative_ids"]) == {"a", "b"}


def test_5_placed_before_prerequisite():
    r = run([S(I("a", deps=("b",)), 1, wave=1), S(I("b"), 2, wave=2)], [F("f1")], [P("p1")])
    (issue,) = [i for i in of(r, coh.DEPENDENCY_ORDER) if i.refs["kind"] == "before_prerequisite"]
    assert issue.refs["initiative_ids"] == ["a", "b"]


def test_5_consistent_order_is_fine():
    r = run([S(I("a", deps=("b",)), 1, wave=2), S(I("b"), 2, wave=1)], [F("f1")], [P("p1")])
    assert not of(r, coh.DEPENDENCY_ORDER)


# 6 -------------------------------------------------------------------------------------------
def test_6_prerequisite_inherits_priority():
    r = run([S(I("a", deps=("b",)), rank=1, wave=2), S(I("b"), rank=3, wave=1)], [F("f1")],
            [P("p1")])
    (issue,) = of(r, coh.INHERITED_PRIORITY)
    assert issue.refs == {"initiative_id": "b", "rank": 3, "inherited_rank": 1}
    chain = next(c for c in r.chains if c.initiative_id == "b")
    assert chain.inherited_rank == 1


def test_6_prerequisite_already_more_prioritary_is_fine():
    r = run([S(I("a", deps=("b",)), rank=2, wave=2), S(I("b"), rank=1, wave=1)], [F("f1")],
            [P("p1")])
    assert not of(r, coh.INHERITED_PRIORITY)


# 7 -------------------------------------------------------------------------------------------
def test_7_tie_is_reported_with_its_rule():
    a, b = I("a", priorities=("p1",)), I("b", priorities=("p2",))
    r = run([S(a, 1, score=0.6), S(b, 2, score=0.6)], [F("f1")], [P("p1", 1), P("p2", 2)])
    (issue,) = of(r, coh.SCORE_TIE)
    assert issue.refs["initiative_ids"] == ["a", "b"] and issue.refs["decided_by"] == "priority_rank"


def test_7_no_tie_no_issue():
    r = run([S(I("a"), 1, score=0.7), S(I("b"), 2, score=0.6)], [F("f1")], [P("p1")])
    assert not of(r, coh.SCORE_TIE)


def test_7_tiebreak_ignores_model_order():
    """Même ensemble, ordre d'entrée inversé : le classement ne bouge pas."""
    crit = scoring.DEFAULT_CRITERIA
    sc = [CriterionScore(key=c.key, value=3, source_ids=[], rationale="") for c in crit]
    a = I("zzz", title="B", priorities=("p2",)).model_copy(update={"scores": sc})
    b = I("aaa", title="A", priorities=("p1",)).model_copy(update={"scores": sc})
    findings, prios = [F("f1")], [P("p1", 1), P("p2", 2)]
    order = []
    for inputs in ([a, b], [b, a]):
        tb = coh.tiebreak_keys(inputs, findings, prios)
        items = scoring.score_with_warnings(inputs, crit, 3, tiebreak=tb)[0]
        order.append([x.initiative.id for x in items])
    assert order[0] == order[1] == ["aaa", "zzz"]  # priorité de rang 1 d'abord, pas l'identifiant


# 8 -------------------------------------------------------------------------------------------
def test_8_missing_duration_gives_order_only():
    a, b = I("a", duration=None), I("b", deps=("a",), duration=4)
    r = run([S(a, 1), S(b, 2, wave=2)], [F("f1")], [P("p1")])
    assert [i.refs["initiative_id"] for i in of(r, coh.NO_DURATION)] == ["a"]
    seq = {s.initiative_id: s for s in r.sequence}
    assert [seq["a"].position, seq["b"].position] == [1, 2]
    assert seq["a"].start_week is None and seq["b"].start_week is None  # aucune date inventée


def test_8_all_durations_known_gives_relative_weeks():
    a, b = I("a", duration=3), I("b", deps=("a",), duration=4)
    r = run([S(a, 1), S(b, 2, wave=2)], [F("f1")], [P("p1")])
    assert not of(r, coh.NO_DURATION)
    seq = {s.initiative_id: s for s in r.sequence}
    assert (seq["a"].start_week, seq["a"].end_week) == (0, 3)
    assert (seq["b"].start_week, seq["b"].end_week) == (3, 7)


# chaîne navigable -------------------------------------------------------------------------------
def test_chain_links_finding_priority_dependency_and_sources():
    ini = I("a", pdeps=("j1",), objective="obj", expected_result="res", indicator="ind")
    r = run([S(ini)], [F("f1", sources=("c1", "c2"))], [P("p1", sources=("c3",))],
            [PJ("j1", "Socle existant")])
    (chain,) = r.chains
    assert [x.id for x in chain.findings] == ["f1"] and [x.id for x in chain.priorities] == ["p1"]
    assert chain.dependencies[0].kind == "project" and chain.dependencies[0].extra["state"] == "in_progress"
    assert chain.source_ids == ["c1", "c2", "c3", "c9"]
    assert (chain.objective, chain.expected_result, chain.indicator) == ("obj", "res", "ind")


def test_all_eight_codes_exist_once():
    assert len(set(coh.CODES)) == 8
