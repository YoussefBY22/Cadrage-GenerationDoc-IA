"""Tests des garde-fous d'entraînement, sans torch ni GPU (mode simulation)."""

import json
import sys

import pytest

from training import export_gguf, guards
from training.dataset.build import build
from training.dataset.filter import check_example, filter_examples
from training.dataset.split import split_by_source
from training.train_lora import (
    DATA_REFUSED,
    EXPORT_FAILED,
    OK,
    REFUSED_BUDGET,
    STOPPED,
    RunConfig,
    SimulatedKill,
    list_valid_checkpoints,
    load_profile,
    run_training,
)


def _examples(n, licence="test", confidential=False):
    meta = {"source": "doc", "licence": licence, "kind": "section", "seed": 1}
    if confidential:
        meta["confidential"] = True
    msgs = [{"role": r, "content": "x"} for r in ("system", "user", "assistant")]
    return [{"messages": msgs, "meta": dict(meta)} for _ in range(n)]


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


@pytest.fixture
def make_cfg(tmp_path):
    def make(profile="pc-nuit", n=1600, run_id="r1", examples=None, **kw):
        train = tmp_path / "train.jsonl"
        val = tmp_path / "val.jsonl"
        _write(train, examples if examples is not None else _examples(n))
        _write(val, _examples(10))
        sim = kw.pop("sim", {})
        return RunConfig(profile=load_profile(profile), run_id=run_id, runs_dir=tmp_path / "runs",
                         train_path=train, val_path=val, simulate=True, sim=sim, **kw)
    return make


def _run_json(cfg):
    return json.loads((cfg.run_dir / "run.json").read_text("utf-8"))


# --- budget -------------------------------------------------------------------------------
def test_refus_si_estimation_depasse_le_budget(make_cfg):
    cfg = make_cfg(budget_hours=1.0)  # 200 pas x 30 s = 1,67 h
    assert run_training(cfg) == REFUSED_BUDGET
    data = _run_json(cfg)
    assert data["status"] == "refused_budget"
    assert data["phases"][0]["name"] == "measure" and data["phases"][0]["steps_measured"] == 50
    assert not list_valid_checkpoints(cfg)  # rien de long n'a démarré


def test_budget_suffisant_termine_et_exporte(make_cfg):
    cfg = make_cfg(budget_hours=3.0)
    assert run_training(cfg) == OK
    names = [p["name"] for p in _run_json(cfg)["phases"]]
    assert names[:2] == ["measure", "trial"] and names[-1] == "final"
    assert _run_json(cfg)["phases"][1]["export_ok"] is True
    export_gguf.verify_export(cfg.run_dir / "export")


# --- reprise ------------------------------------------------------------------------------
def test_reprise_apres_arret_simule(make_cfg):
    cfg = make_cfg(budget_hours=3.0, sim={"kill_at": 130})
    with pytest.raises(SimulatedKill):
        run_training(cfg)
    last = list_valid_checkpoints(cfg)[-1]
    saved_step = json.loads((last / "state.json").read_text())["step"]
    assert 0 < saved_step < 130 and len(list_valid_checkpoints(cfg)) <= 3
    cfg2 = make_cfg(budget_hours=3.0)  # même run-id, sans panne
    assert run_training(cfg2) == OK
    data = _run_json(cfg2)
    assert data["resumed_from_step"] == saved_step and data["attempts"] == 2
    assert data["status"] == "completed"


def test_point_de_reprise_incomplet_ignore(make_cfg):
    cfg = make_cfg(budget_hours=3.0, sim={"kill_at": 130})
    with pytest.raises(SimulatedKill):
        run_training(cfg)
    partial = cfg.run_dir / "checkpoints" / "step-0009999"
    partial.mkdir()  # sans COMPLETE : coupure pendant l'écriture
    assert partial not in list_valid_checkpoints(cfg)
    assert run_training(make_cfg(budget_hours=3.0)) == OK


# --- arrêts propres -----------------------------------------------------------------------
def test_arret_sur_nan_avec_point_de_reprise(make_cfg):
    cfg = make_cfg(budget_hours=3.0, sim={"nan_at": 120})
    assert run_training(cfg) == STOPPED
    data = _run_json(cfg)
    assert data["status"] == "stopped" and "invalide" in data["stop_reason"]
    assert list_valid_checkpoints(cfg)


def test_arret_disque_plein_simule(make_cfg):
    cfg = make_cfg(budget_hours=3.0, sim={"disk_full_at": 60})
    assert run_training(cfg) == STOPPED
    assert "disque" in _run_json(cfg)["stop_reason"]
    assert list_valid_checkpoints(cfg)


def test_arret_temperature_gpu(make_cfg):
    cfg = make_cfg(budget_hours=3.0, sim={"hot_at": 70})
    assert run_training(cfg) == STOPPED
    assert "chaud" in _run_json(cfg)["stop_reason"]


def test_arret_demande_par_signal(make_cfg):
    cfg = make_cfg(budget_hours=3.0)
    stop = guards.StopFlag()
    stop.request()
    assert run_training(cfg, stop) == STOPPED
    assert "utilisateur" in _run_json(cfg)["stop_reason"]


def test_gardes_unitaires():
    assert guards.check_loss(float("inf"), 1.0)
    assert guards.check_loss(3.5, 1.0) and guards.check_loss(2.9, 1.0) is None
    assert guards.check_disk(sys.path and __import__("pathlib").Path("."), 5, lambda _p: 1.0)
    assert guards.check_temperature(83, lambda: 90.0) and guards.check_temperature(83, lambda: None) is None


def test_arret_anticipe_sur_plateau(make_cfg):
    cfg = make_cfg(budget_hours=3.0, sim={"plateau_at": 40})
    assert run_training(cfg) == OK
    assert any(p["name"] == "early_stop" for p in _run_json(cfg)["phases"])


# --- export -------------------------------------------------------------------------------
def test_export_invalide_detecte(tmp_path):
    (tmp_path / "adapter.gguf").write_bytes(b"pas du gguf")
    (tmp_path / "Modelfile").write_text("FROM x\nADAPTER adapter.gguf\n")
    with pytest.raises(export_gguf.ExportError):
        export_gguf.verify_export(tmp_path)


def test_export_reel_sans_llama_cpp_refuse(tmp_path, monkeypatch):
    monkeypatch.delenv("LLAMA_CPP_DIR", raising=False)
    with pytest.raises(export_gguf.ExportError):
        export_gguf.export(tmp_path, tmp_path / "o", simulate=False)


def test_echec_export_dans_l_essai_empeche_le_long_entrainement(make_cfg, monkeypatch):
    def boom(*a, **k):
        raise export_gguf.ExportError("test")
    monkeypatch.setattr(export_gguf, "export", boom)
    cfg = make_cfg(budget_hours=3.0)
    assert run_training(cfg) == EXPORT_FAILED
    assert not list_valid_checkpoints(cfg)


# --- données et journal -------------------------------------------------------------------
def test_donnees_sans_licence_refusees(make_cfg):
    cfg = make_cfg(budget_hours=3.0, examples=_examples(50, licence=""))
    assert run_training(cfg) == DATA_REFUSED


def test_profil_colab_refuse_donnees_confidentielles(make_cfg):
    cfg = make_cfg(profile="colab", budget_hours=3.0, examples=_examples(50, confidential=True))
    assert run_training(cfg) == DATA_REFUSED
    assert "confidentiel" in _run_json(cfg)["stop_reason"]


def test_run_json_complet(make_cfg):
    cfg = make_cfg(budget_hours=3.0)
    assert run_training(cfg) == OK
    d = _run_json(cfg)
    for key in ("run_id", "seed", "params", "versions", "hardware", "data_hashes", "phases",
                "metrics", "duration_seconds", "status", "started_at"):
        assert key in d, key
    assert d["seed"] == 7 and d["params"]["lora"]["r"] == 16 and d["params"]["lr"] == 2e-4
    assert d["versions"]["python"] and set(d["data_hashes"]) == {"train", "val"}
    assert all(len(h) == 64 for h in d["data_hashes"].values())
    assert d["metrics"] and d["duration_seconds"] > 0


def test_simulation_n_importe_pas_torch(make_cfg):
    run_training(make_cfg(budget_hours=3.0))
    assert not {"torch", "peft", "trl", "transformers"} & set(sys.modules)


# --- jeu d'entraînement -------------------------------------------------------------------
@pytest.fixture(scope="module")
def candidates():
    return build(3)


def test_filtre_garde_les_exemples_verifies(candidates):
    kept, rejects = filter_examples(candidates)
    assert len(kept) == len(candidates) and not rejects
    assert all("_verif" not in e and e["meta"]["licence"] for e in kept)
    assert {e["meta"]["kind"] for e in kept} >= {"section", "refus"}


def test_filtre_rejette_licence_absente_et_phrase_non_verifiee(candidates):
    bad = json.loads(json.dumps(candidates[0]))
    bad["meta"]["licence"] = ""
    assert check_example(bad)[0] is False
    bad2 = json.loads(json.dumps(next(c for c in candidates if c["meta"]["kind"] == "section")))
    answer = json.loads(bad2["messages"][2]["content"])
    answer["sentences"][0]["sources"] = ["P9"]  # étiquette inexistante : phrase non vérifiée
    bad2["messages"][2]["content"] = json.dumps(answer, ensure_ascii=False)
    assert check_example(bad2)[0] is False


def test_prompt_identique_a_l_inference(candidates):
    from app.generation.prompting import SYSTEM_PROMPT_FR
    assert all(c["messages"][0]["content"] == SYSTEM_PROMPT_FR for c in candidates)


def test_decoupage_aucun_document_dans_deux_jeux(candidates):
    kept, _ = filter_examples(candidates)
    parts = split_by_source(kept, seed=7)
    srcs = {k: {e["meta"]["source"] for e in v} for k, v in parts.items()}
    assert all(srcs.values())
    assert not (srcs["train"] & srcs["val"] or srcs["train"] & srcs["test"]
                or srcs["val"] & srcs["test"])
    assert sum(len(v) for v in parts.values()) == len(kept)
    assert split_by_source(kept, seed=7) == parts  # déterministe


def test_graines_differentes_de_l_evaluation(candidates):
    assert all(c["meta"]["seed"] != 7 for c in candidates)
