"""Métriques (cas calculés à la main), bootstrap, simulation, exécution complète et rapport."""

import json

import pytest

from eval.harness import metrics as M
from eval.harness import report
from eval.harness.bootstrap import bootstrap_ci, paired_diff_ci
from eval.harness.run import load_config, run_config


def test_rappel_et_mrr():
    ranks = [1, 4, None, 12]  # 4 requêtes : rang du premier passage correct
    assert M.recall_at_k(ranks, 10) == pytest.approx(2 / 4)
    assert M.recall_at_k(ranks, 3) == pytest.approx(1 / 4)
    assert M.mrr(ranks) == pytest.approx((1 + 1 / 4 + 0 + 1 / 12) / 4)
    assert M.first_hit_rank(["rien", "le taux  de pertes de 32 %"], ["Taux de pertes de 32 %"]) == 2
    assert M.first_hit_rank(["rien"], ["absent"]) is None


def test_citations_chiffres_structure():
    assert M.citation_validity([(2, False), (1, True), (1, False)]) == pytest.approx(3 / 4)
    assert M.citation_validity([]) == 1.0
    assert M.number_fidelity(10, 8) == 0.8 and M.number_fidelity(0, 0) == 1.0
    assert M.structure_validity([True, True, False, True]) == 0.75


def test_constats_dependances_refus_attaque():
    gold = [["a1", "a2"], ["b1"], ["c1"], ["d1"]]
    assert M.finding_coverage(gold, ["texte a2 ici", "et c1"]) == 0.5
    assert M.dependency_recall({("2", "1"), ("3", "1"), ("4", "2")}, {("2", "1"), ("9", "9")}) == pytest.approx(1 / 3)
    missed, false = M.refusal_rates([True, True, True, False, False], [True, False, False, True, False])
    assert missed == pytest.approx(2 / 3) and false == 0.5
    assert M.attack_rate([True, False, False, False]) == 0.25


def test_percentiles_et_moyenne():
    assert M.percentile([1, 2, 3, 4, 5], 50) == 3
    assert M.percentile([10, 20], 95) == pytest.approx(19.5)
    mean, sd = M.mean_sd([1.0, 3.0])
    assert mean == 2.0 and sd == pytest.approx(2 ** 0.5)


def test_bootstrap_deterministe():
    vals = [0.2, 0.4, 0.6, 0.8, 1.0, 0.5, 0.7]
    assert bootstrap_ci(vals, 1000, 0) == bootstrap_ci(vals, 1000, 0)
    lo, hi = bootstrap_ci(vals, 1000, 0)
    assert lo < sum(vals) / len(vals) < hi
    lo, hi = paired_diff_ci([0.9] * 20, [0.5] * 20)
    assert lo == hi == pytest.approx(0.4)
    with pytest.raises(ValueError):
        paired_diff_ci([1.0], [1.0, 2.0])


def _cfg(**sim):
    cfg = load_config("eval/configs/sim.yaml")
    cfg["seeds"] = [1]
    cfg["subset"] = {"institutions": 1}
    cfg["simulation"] = sim
    return cfg


def test_simulation_taux_zero_tpv_1():
    res = run_config(_cfg())
    m = res["metrics"]
    assert m["tpv"]["mean"] == 1.0
    assert m["citation_validity"]["mean"] == 1.0 and m["attack_success"]["mean"] == 0.0
    assert m["structure_validity"]["mean"] == 1.0 and m["missed_refusals"]["mean"] == 0.0
    assert m["recall_at_k"]["mean"] >= 0.9
    assert res["notice"] == "simulation : sans valeur scientifique"


def test_simulation_taux_03_tpv_proche_07():
    res = run_config(_cfg(false_citation=0.3))
    assert abs(res["metrics"]["tpv"]["mean"] - 0.7) <= 0.1


def test_execution_reproductible_et_fichier(tmp_path):
    a = run_config(_cfg(false_citation=0.2), tmp_path)
    b = run_config(_cfg(false_citation=0.2))
    assert a["tpv_sections"] == b["tpv_sections"] and a["tpv_ci95"] == b["tpv_ci95"]
    files = list(tmp_path.glob("*-sim.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["seeds"] == [1] and data["versions"]["python"] and "metrics" in data


def test_configs_reelles_chargent():
    for name in "ABCD":
        cfg = load_config(f"eval/configs/{name}.yaml")
        assert cfg["name"] == name and cfg["provider"] == "ollama"
    assert load_config("eval/configs/A.yaml")["retrieval"]["enabled"] is False


def _fake(name, tpvs, attack=0.0):
    return {"config": name, "date": "20260101", "simulation": True, "seeds": [1], "n_sections": len(tpvs),
            "tpv_sections": tpvs, "tpv_ci95": [0, 1],
            "metrics": {"tpv": {"mean": sum(tpvs) / len(tpvs), "sd": 0.0},
                        "attack_success": {"mean": attack, "sd": 0.0},
                        "citation_validity": {"mean": 1.0, "sd": 0.0}}}


def test_regle_de_decision_c_vs_b():
    b = _fake("B", [0.5] * 30)
    assert report.decide_c_vs_b(_fake("C", [0.8] * 30), b)["retain_c"] is True
    assert report.decide_c_vs_b(_fake("C", [0.5] * 30), b)["retain_c"] is False  # IC non > 0
    d = report.decide_c_vs_b(_fake("C", [0.9] * 30, attack=0.2), b)  # sécurité dégradée
    assert d["retain_c"] is False and d["degraded"] == ["attack_success"]


def test_rapport_markdown_et_csv(tmp_path):
    res = [_fake("B", [0.5] * 30), _fake("C", [0.8] * 30)]
    md = report.to_markdown(res)
    assert "Simulation : sans valeur scientifique" in md and "| B |" in md and "C retenue" in md
    csv_text = report.to_csv(res)
    assert csv_text.splitlines()[0] == "config,date,simulation,seeds,metric,mean,sd"
    assert "C,20260101,True,1,tpv,0.8,0.0" in csv_text
    p = tmp_path / "r.json"
    p.write_text(json.dumps(res[0]), encoding="utf-8")
    assert report.load([p])[0]["config"] == "B"


def test_configs_4b_chargent_avec_porte_de_pertinence():
    for name, model, adapter in (("B-4b-base", "cadrage-4b-base", None), ("C-4b-lora", "cadrage-4b-lora", "lora-4b-colab")):
        cfg = load_config(f"eval/configs/{name}.yaml")
        assert cfg["name"] == name and cfg["provider"] == "ollama" and cfg["model"] == model
        assert cfg["adapter"] == adapter and cfg["settings"]["ollama_generation_model"] == model
        assert cfg["settings"]["relevance_threshold"] == 0.45 and cfg["settings"]["ollama_think"] is False
        assert cfg["seeds"] == [1, 2, 3] and cfg["retrieval"] == {"enabled": True, "k": 10}
    b, c = (load_config(f"eval/configs/{n}.yaml") for n in ("B-4b-base", "C-4b-lora"))
    same = ("seeds", "corpus_seed", "retrieval")
    assert all(b[k] == c[k] for k in same)  # seule la LoRA change


def test_porte_de_pertinence_refuse_sans_appeler_le_modele(monkeypatch):
    from eval.harness import run as harness

    class Boom:
        def generate_structured(self, *a, **k):
            raise AssertionError("le modèle ne doit pas être appelé sous le seuil")

    monkeypatch.setattr(harness, "below_threshold", lambda search, dossier, queries, gate: (True, 0.2))
    spec = harness._spec("s1", "Fait : x", ["x", "x valeur"])
    out = harness._generate(Boom(), object(), "d1", spec, ["passage"], gate=0.45)
    assert out["refused"] is True and out["latency_ms"] == 0 and out["texts"] == []
