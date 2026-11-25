"""Entraînement en parties : ordre, coupures, reprise, arrêt anticipé, export (simulation, sans GPU ni réseau)."""

import hashlib
import json
import math
from pathlib import Path

import pytest

from training import export_gguf, guards, parts
from training.train_lora import (
    OK,
    STOPPED,
    RunConfig,
    SimBackend,
    SimulatedKill,
    load_profile,
    render_prompt,
    total_steps,
)

N_TRAIN = 40  # 40 exemples x 3 époques / (1 x 4) = 30 pas, 2 parties de 15 pas


def _rows(n, licence="CC BY 4.0 (test)", **meta):
    msgs = [{"role": r, "content": "x"} for r in ("system", "user", "assistant")]
    return [{"messages": msgs, "meta": {"licence": licence, "source": "doc", **meta}} for _ in range(n)]


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


@pytest.fixture
def env(tmp_path):
    train, val = tmp_path / "train.jsonl", tmp_path / "val.jsonl"
    _write(train, _rows(N_TRAIN))
    _write(val, _rows(8))

    def cfg(machine="vm1", **sim):
        return RunConfig(profile=_small_profile(), run_id="r", runs_dir=tmp_path / machine,
                         train_path=train, val_path=val, save_every_min=5, min_free_gb=0.001,
                         simulate=True, sim=sim)
    return cfg, tmp_path / "drive", train


def _small_profile() -> dict:
    """Le vrai profil, avec 2 parties et une mesure tous les 4 pas : adapté au jeu de 40 exemples de ces tests."""
    return {**load_profile("colab-parties"), "parts": 2, "eval_every": 4}


def _step(store):
    return parts.Store(store).latest()[1]["state"]["step"]


def _state(store):
    return parts.Store(store).latest()[1]["state"]


def test_profil_qwen3_4b_epingle_et_prudent():
    p = load_profile("colab-parties")
    assert p["base_model"] == "Qwen/Qwen3-4B" and len(p["base_revision"]) == 40
    assert p["quant"] == "nf4_double" and p["epochs"] <= 3 and p["lr"] <= 1e-4
    assert p["eval_every"] and p["early_stop_patience"] == 2 and p["base_tag"] == "qwen3:4b"
    assert p["parts"] == 3 and p["eval_every"] == 20 and parts.bounds(30, p["parts"]) == [0, 10, 20, 30]


def test_refus_sans_partie_0(env):
    cfg, store, _ = env
    with pytest.raises(parts.Refused, match="partie 0"):
        parts.train_part(cfg(), store, 1)


def test_deux_parties_sur_deux_machines_puis_export(env):
    cfg, store, _ = env
    assert parts.prove(cfg(), store) == OK
    for k in (1, 2):
        assert parts.train_part(cfg(f"vm{k}"), store, k) == OK  # disque local neuf à chaque fois
        assert _step(store) == 15 * k
    evals = _state(store)["evals"]
    assert [e["step"] for e in evals] == [0, 4, 8, 12, 15, 16, 20, 24, 28, 30]
    assert parts.export_latest(cfg("vm3"), store, "lora") == OK
    assert parts.export_latest(cfg("vm3"), store, "base") == OK
    for name in ("cadrage-4b-lora", "cadrage-4b-base"):
        export_gguf.verify_export(store / "modeles" / name)
    sums = (store / "modeles" / "SHA256SUMS.txt").read_text("utf-8").splitlines()
    assert len(sums) == 2 and all("model.gguf" in line for line in sums)


def test_memes_pas_avec_ou_sans_coupure(env, monkeypatch):
    cfg, store, _ = env
    seen, real = [], SimBackend.train_step

    def spy(self, step):
        loss = real(self, step)
        seen.append(step)
        return loss

    parts.prove(cfg(), store)
    monkeypatch.setattr(SimBackend, "train_step", spy)
    with pytest.raises(SimulatedKill):
        parts.train_part(cfg("vm1", kill_at=13), store, 1)
    saved = _step(store)
    assert 12 - saved <= 10  # au plus 5 min perdues (30 s par pas simulé)
    seen.clear()
    assert parts.train_part(cfg("vm2"), store, 1) == OK
    assert seen == list(range(saved, 15))


def test_ordre_impose_et_partie_rejouee(env):
    cfg, store, _ = env
    parts.prove(cfg(), store)
    with pytest.raises(parts.Refused, match="partie 1"):
        parts.train_part(cfg(), store, 2)
    assert parts.train_part(cfg(), store, 1) == OK
    serial = parts.Store(store).latest()[1]["serial"]
    assert parts.train_part(cfg(), store, 1) == OK
    assert parts.Store(store).latest()[1]["serial"] == serial


def test_coupure_pendant_la_mesure_de_fin_de_partie(env, monkeypatch):
    cfg, store, _ = env
    parts.prove(cfg(), store)
    real = SimBackend.evaluate

    def cut(self, step):
        if step == 15:
            raise SimulatedKill("coupure")
        return real(self, step)

    monkeypatch.setattr(SimBackend, "evaluate", cut)
    with pytest.raises(SimulatedKill):
        parts.train_part(cfg(), store, 1)
    monkeypatch.setattr(SimBackend, "evaluate", real)
    with pytest.raises(parts.Refused, match="partie 1"):
        parts.train_part(cfg(), store, 2)
    assert parts.train_part(cfg("vm2"), store, 1) == OK
    assert parts.train_part(cfg("vm2"), store, 2) == OK


# ---------------------------------------------------------------- arrêt si la perte de validation remonte
def _rising_from(step0, monkeypatch):
    def evaluate(self, step):
        return 1.0 - 0.05 * min(step, step0) + 0.02 * max(0, step - step0)

    monkeypatch.setattr(SimBackend, "evaluate", evaluate)


def test_arret_anticipe_quand_la_validation_remonte(env, monkeypatch):
    cfg, store, _ = env
    parts.prove(cfg(), store)
    _rising_from(4, monkeypatch)  # meilleure au pas 4, puis elle remonte aux pas 8 et 12
    assert parts.train_part(cfg(), store, 1) == OK
    state = _state(store)
    assert state["stopped_early"] and state["step"] == 12
    assert state["best"]["step"] == 4 and state["bad_evals"] == 2
    steps_before = _step(store)
    assert parts.train_part(cfg("vm2"), store, 2) == OK  # rien à refaire : arrêt déjà décidé
    assert _step(store) == steps_before


def test_export_prend_le_meilleur_adaptateur_pas_le_dernier(env, monkeypatch):
    cfg, store, _ = env
    parts.prove(cfg(), store)
    _rising_from(4, monkeypatch)
    parts.train_part(cfg(), store, 1)
    assert parts.Store(store / "meilleur").latest()[1]["state"]["step"] == 4
    used = []
    real = export_gguf.export

    def spy(adapter, out, *a, **k):
        used.append(adapter)
        return real(adapter, out, *a, **k)

    monkeypatch.setattr(export_gguf, "export", spy)
    assert parts.export_latest(cfg("vm2"), store, "lora") == OK
    assert used[0].parent.name == "a-exporter-meilleur"
    assert parts.export_latest(cfg("vm2"), store, "base") == OK
    assert used[1] is None  # la base passe par la même chaîne, sans adaptateur


def test_sans_remontee_pas_d_arret(env):
    cfg, store, _ = env
    parts.prove(cfg(), store)
    assert parts.train_part(cfg(), store, 1) == OK
    assert not _state(store).get("stopped_early") and _state(store)["step"] == 15


def test_sauvegarde_corrompue_on_prend_la_precedente(env):
    cfg, store, _ = env
    parts.prove(cfg(), store)
    parts.train_part(cfg(), store, 1)
    newest, manifest = parts.Store(store).latest()
    (store / newest / next(iter(manifest["files"]))).write_text("tronqué", encoding="utf-8")
    slot, previous = parts.Store(store).latest()
    assert slot != newest and previous["serial"] == manifest["serial"] - 1
    assert parts.train_part(cfg("vm2"), store, 1) == OK


def test_perte_invalide_jamais_sauvegardee(env):
    cfg, store, _ = env
    parts.prove(cfg(), store)
    assert parts.train_part(cfg("vm1", nan_at=12), store, 1) == STOPPED
    last = _state(store)
    assert last["step"] < 12 and math.isfinite(last["initial_loss"])


def test_arret_demande_sauvegarde(env):
    cfg, store, _ = env
    parts.prove(cfg(), store)
    stop = guards.StopFlag()
    stop.request()
    assert parts.train_part(cfg(), store, 1, stop) == STOPPED
    assert _step(store) == 1


def test_trop_chaud_sauvegarde_puis_arret(env):
    cfg, store, _ = env
    parts.prove(cfg(), store)
    assert parts.train_part(cfg("vm1", hot_at=10), store, 1) == STOPPED
    assert _step(store) == 10


def test_donnees_changees_refusees(env):
    cfg, store, train = env
    parts.prove(cfg(), store)
    _write(train, _rows(N_TRAIN - 1))
    with pytest.raises(parts.Refused, match="différents"):
        parts.train_part(cfg(), store, 1)


@pytest.mark.parametrize("rows", [_rows(20, licence="interne client"), _rows(20, confidential=True)])
def test_rien_de_non_public_sur_colab(env, rows):
    cfg, store, train = env
    _write(train, rows)
    with pytest.raises(parts.Refused) as e:
        parts.prove(cfg(), store)
    assert e.value.code == parts.DATA_REFUSED


@pytest.mark.parametrize("licence", ["CC BY 4.0 (test)", "Licence Ouverte 2.0 (Etalab)",
                                     "Décision 2011/833/UE (réutilisation, CC BY 4.0)"])
def test_licences_ouvertes_acceptees(licence):
    parts.check_public({"public_data_only": True}, _rows(2, licence=licence))


def test_export_rate_bloque_les_parties(env, monkeypatch):
    cfg, store, _ = env

    def boom(*_a, **_k):
        raise export_gguf.ExportError("LoRA adapters are no longer supported")

    monkeypatch.setattr(export_gguf, "export", boom)
    with pytest.raises(parts.Refused, match="export"):
        parts.prove(cfg(), store)
    with pytest.raises(parts.Refused, match="partie 0"):
        parts.train_part(cfg(), store, 1)


# ---------------------------------------------------------------- invite et Modelfile
def test_invite_identique_a_ollama():
    # rendu relevé sur Ollama 0.40.17, qwen3:4b, think=false (_debug_render_only), le 23/11/2026
    assert render_prompt("SYS", "USR") == (
        "<|im_start|>system\nSYS\n\n<|im_end|>\n<|im_start|>user\nUSR<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n")


def test_modelfile_fige_de_qwen3_4b():
    body = export_gguf.MODELFILE.read_bytes()
    assert hashlib.sha256(body).hexdigest() == "85c0f464ee5bd6b75045c0ea61d5120ec6b54aa1ae5967015b05a7f07fbac502"
    assert b"\r\n" not in body and b"FROM " not in body and b"LICENSE" not in body
    text = export_gguf.modelfile_text(export_gguf.base_modelfile_text(), "model.gguf")
    assert text.startswith("FROM ./model.gguf\n") and "PARAMETER temperature 0.6" in text
    assert "PARAMETER stop <|im_end|>" in text and "ADAPTER" not in text and text.endswith('Qwen3-4B)"\n')


def test_modelfile_sans_adapter_et_en_lf(tmp_path):
    text = export_gguf.modelfile_text('# commentaire\nFROM C:\\blob\nTEMPLATE """x"""\nLICENSE """long', "model.gguf")
    assert 'TEMPLATE """x"""' in text and "blob" not in text and "long" not in text
    export_gguf.export(None, tmp_path / "o", simulate=True)
    assert b"\r\n" not in (tmp_path / "o" / "Modelfile").read_bytes()
    export_gguf.verify_export(tmp_path / "o")


def test_empreinte_obligatoire_et_verifiee(tmp_path):
    export_gguf.export(None, tmp_path / "o", simulate=True)
    (tmp_path / "o" / "model.gguf").write_bytes(b"GGUF\x00autre")
    with pytest.raises(export_gguf.ExportError, match="SHA-256"):
        export_gguf.verify_export(tmp_path / "o")


def test_gabarit_ollama_different_refuse(monkeypatch):
    monkeypatch.setattr(export_gguf, "_run", lambda *a, **k: 'FROM x\nTEMPLATE """autre"""\n')
    with pytest.raises(export_gguf.ExportError, match="diffère"):
        export_gguf.check_template()
    monkeypatch.setattr(export_gguf, "_run", lambda *a, **k: "FROM x\n" + export_gguf.base_modelfile_text() + "LICENSE y")
    export_gguf.check_template()


def test_chaine_f16_puis_q4_k_m_meme_pour_la_base(tmp_path, monkeypatch):
    llama = tmp_path / "llama.cpp"
    (llama / "build/bin").mkdir(parents=True)
    (llama / "convert_hf_to_gguf.py").write_text("", encoding="utf-8")
    (llama / "build/bin/llama-quantize").write_text("", encoding="utf-8")
    monkeypatch.setenv("LLAMA_CPP_DIR", str(llama))
    monkeypatch.setattr(export_gguf, "check_template", lambda tag="qwen3:4b": None)
    calls = []

    def fake_run(cmd, what, cwd=None):
        calls.append(cmd)
        if "--outfile" in cmd:
            Path(cmd[cmd.index("--outfile") + 1]).write_bytes(b"GGUF" + b"f16")
        elif cmd[0].endswith("llama-quantize"):
            Path(cmd[2]).write_bytes(b"GGUF" + b"q4")
        return ""

    monkeypatch.setattr(export_gguf, "_run", fake_run)
    out = export_gguf.export(None, tmp_path / "base", "qwen3:4b", False, tmp_path / "hf")
    convert, quant = calls
    assert convert[convert.index("--outtype") + 1] == "f16" and str(tmp_path / "hf") in convert
    assert quant[0].endswith("llama-quantize") and quant[-1] == "Q4_K_M"
    assert not (out / "model-f16.gguf").exists()  # l'intermédiaire de 8 Go ne reste pas
    export_gguf.verify_export(out)
    assert (out / "model.gguf.sha256").read_text("utf-8").split()[0] == hashlib.sha256(b"GGUFq4").hexdigest()


def test_quantize_manquant_message_clair(tmp_path):
    with pytest.raises(export_gguf.ExportError, match="Compiler llama.cpp"):
        export_gguf.quantize_tool(tmp_path)


def test_compilation_seulement_de_llama_quantize(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, what, cwd=None):
        calls.append(cmd)
        if "--build" in cmd:
            (tmp_path / "build/bin").mkdir(parents=True)
            (tmp_path / "build/bin/llama-quantize").write_text("", encoding="utf-8")
        return ""

    monkeypatch.setattr(export_gguf, "_run", fake_run)
    tool = export_gguf.build_quantize(tmp_path)
    assert tool.name == "llama-quantize" and "-DGGML_CUDA=OFF" in calls[0]
    assert calls[1][calls[1].index("--target") + 1] == "llama-quantize"
    assert export_gguf.build_quantize(tmp_path) == tool and len(calls) == 2  # déjà compilé : rien à refaire
