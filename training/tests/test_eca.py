"""Rapports de la Cour : lecture, exemples des cinq tâches et découpage par rapport (texte synthétique, sans réseau)."""

from __future__ import annotations

import json
import random

from training.dataset import assemble, eca_build, eca_parse, schema_order
from training.dataset.v3_build import rerender

REPORT = """
12 Nous avons constaté que la Commission n’a pas suivi les délais prévus pour les contrôles de conformité des
États membres, ce qui retarde la détection des manquements dans plusieurs secteurs de l’économie européenne.

13 Les directions générales ne disposent pas de données suffisantes pour évaluer l’effet des mesures adoptées
et nous avons relevé que l’information transmise aux États membres reste incomplète sur plusieurs points.

14 Nous avons observé que l’absence d’indicateurs de résultats empêche de mesurer les progrès accomplis dans la
mise en œuvre du programme, et le suivi reste insuffisant pour corriger les écarts.

Recommandation n° 1 – Améliorer le suivi des contrôles

La Commission devrait améliorer le suivi des contrôles:

a) en enregistrant les dates de début et de fin de tous les contrôles;

b) en publiant chaque année un rapport sur les délais de traitement.

Quand? D’ici à fin 2026.

Recommandation n° 2 – Renforcer les données

La Commission devrait renforcer la qualité des données transmises par les États membres et leur partage.

Quand? D’ici à fin 2025.

Recommandation n° 3 – Mesurer les résultats

La Commission devrait définir des indicateurs de résultats pour le programme.

Quand? En 2027.
"""

REPLY = """
Recommandation nº 1 - Améliorer le suivi des contrôles

La Commission accepte la recommandation nº 1 a), car elle est conforme à la pratique actuelle des services.

La Commission accepte partiellement la recommandation nº 1 b). La publication annuelle ferait peser une charge
disproportionnée sur les services, qui disposent de ressources limitées. Elle publiera un rapport tous les trois ans.

Recommandation nº 2 - Renforcer les données

La Commission n’accepte pas la recommandation nº 2. Les États membres sont seuls responsables de leurs données.

Recommandation nº 3 - Mesurer les résultats

La Commission accepte la recommandation nº 3. Elle définira des indicateurs dans le cadre de son évaluation.
"""


def _report(i: int = 0):
    def uniq(t: str) -> str:  # rapports différents : aucun passage identique d'un rapport à l'autre
        return t.replace("contrôles", f"contrôles{i}").replace("données", f"données{i}").replace("résultats", f"résultats{i}")

    return {"id": "eca-sr-2099-01", "url": "https://www.eca.europa.eu/x.pdf", "text": uniq(REPORT), "reply_text": uniq(REPLY),
            "titre": "Rapport spécial 01/2099", "reponse": {"id": "r"}, "year": 2099, "number": 1}


def test_recommendations_and_deadlines_are_read_as_published():
    recs = eca_parse.recommendations(REPORT)
    assert [r.number for r in recs] == [1, 2, 3]
    assert recs[0].quand == "D’ici à fin 2026." and [a for a, _ in recs[0].items] == ["a", "b"]
    assert recs[1].lead.startswith("La Commission devrait renforcer") and not recs[1].items


def test_positions_follow_the_official_wording():
    pos = eca_parse.positions(REPLY)
    assert [(p.stance, p.letters) for p in pos[1]] == [("accept", ["a"]), ("partial", ["b"])]
    assert pos[2][0].stance == "reject" and pos[3][0].stance == "accept"


def test_every_task_is_built_verified_and_ordered():
    exs = eca_build.build_report(_report())
    tasks = {e["meta"]["task_type"] for e in exs}
    assert {"feuille_de_route", "extraction", "position", "conflit", "refus"} <= tasks
    for e in exs:
        answer = json.loads(e["messages"][2]["content"])
        model = eca_build.LLMFindings if "findings" in answer else (
            eca_build.LLMStance if e["meta"]["rendu"]["tache"] in ("position", "conflict") else eca_build.LLMSection)
        assert schema_order.is_ordered(model, answer)
        assert e["meta"]["tpv"] == 1 and not e["meta"]["bloquants"]
        assert rerender(e) == e["messages"][1]["content"]  # l'invite est reproductible depuis meta.rendu
        assert e["meta"]["licence"].startswith("CC BY 4.0")


def test_position_label_is_the_official_answer_and_conflict_needs_a_reason():
    exs = eca_build.build_report(_report())
    for e in exs:
        if e["meta"]["task_type"] == "position":
            assert json.loads(e["messages"][2]["content"])["stance"] == e["meta"]["position_officielle"]
        if e["meta"]["task_type"] == "conflit":
            stance = json.loads(e["messages"][2]["content"])["stance"]
            assert stance in ("conflict", "aligned") and e["meta"]["position_officielle"] in ("partial", "reject", "accept")
            assert (stance == "aligned") == (e["meta"]["position_officielle"] == "accept")


def test_refusals_remove_the_evidence_and_say_what_is_missing():
    refs = [e for e in eca_build.build_report(_report()) if e["meta"]["task_type"] == "refus"]
    assert refs
    for e in refs:
        a = json.loads(e["messages"][2]["content"])
        assert a == {"status": "insufficient_evidence", "sentences": [], "missing_evidence": eca_build.MISSING[e["meta"]["refus_type"]]}
        if e["meta"]["refus_type"] == "position":  # la réponse de la Commission n'est pas dans les passages
            assert "La Commission accepte" not in e["messages"][1]["content"]


def test_roadmap_never_invents_a_date():
    for e in eca_build.build_report(_report()):
        if e["meta"]["task_type"] != "feuille_de_route":
            continue
        out = json.loads(e["messages"][2]["content"])
        passages = " ".join(p["texte"] for p in e["meta"]["rendu"]["passages"])
        for s in out["sentences"]:
            if s["kind"] == "fact":
                assert s["text"] in passages


def test_split_is_by_report_and_meets_minimums():
    rows = []
    for i in range(40):
        rep = {**_report(i), "id": f"eca-sr-2099-{i:02d}"}
        rows += assemble.pick(eca_build.build_report(rep))
    before = [e["meta"]["id"] for e in rows]
    assemble.assign_splits(rows)
    sides: dict[str, set[str]] = {}
    for r in rows:
        sides.setdefault(assemble.group_of(r["meta"]["source"]), set()).add(r["meta"]["split"])
    assert all(len(v) == 1 for v in sides.values())
    assert {r["meta"]["split"] for r in rows} == {"train", "val", "test"}
    assert assemble.group_of("eca-rep-sr-2024-27") == assemble.group_of("eca-sr-2024-27")
    random.Random(0)  # déterministe : deux tirages identiques
    again = []
    for i in range(40):
        again += assemble.pick(eca_build.build_report({**_report(i), "id": f"eca-sr-2099-{i:02d}"}))
    assert before == [e["meta"]["id"] for e in again]
