"""Entraînement en parties : ordre, coupures, reprise, export (simulation, sans GPU ni réseau)."""

import json
import math

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
)


def _rows(n, licence="CC BY 3.0 IGO", **meta):
    msgs = [{"role": r, "content": "x"} for r in ("system", "user", "assistant")]
    return [{"messages": msgs, "meta": {"licence": licence, "source": "doc", **meta}} for _ in range(n)]


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


@pytest.fixture
def env(tmp_path):
    train, val = tmp_path / "train.jsonl", tmp_path / "val.jsonl"
    _write(train, _rows(1000))
    _write(val, _rows(8))

    def cfg(machine="vm1", **sim):
        return RunConfig(profile=load_profile("colab-parties"), run_id="r", runs_dir=tmp_path / machine,
                         train_path=train, val_path=val, save_every_min=5, min_free_gb=0.001,
                         simulate=True, sim=sim)
    return cfg, tmp_path / "drive", train


def _step(store):
    return parts.Store(store).latest()[1]["state"]["step"]


def test_bornes():
    assert parts.bounds(200, 4) == [0, 50, 100, 150, 200]
    assert parts.bounds(199, 4)[-1] == 199


def test_refus_sans_partie_0(env):
    cfg, store, _ = env
    with pytest.raises(parts.Refused, match="partie 0"):
        parts.train_part(cfg(), store, 1)


def test_quatre_parties_sur_quatre_machines(env):
    cfg, store, _ = env
    assert parts.prove(cfg(), store) == OK
    for k in range(1, 5):
        assert parts.train_part(cfg(f"vm{k}"), store, k) == OK  # disque local neuf à chaque fois
        assert _step(store) == 50 * k
    evals = parts.Store(store).latest()[1]["state"]["evals"]
    assert [e["step"] for e in evals] == [0, 50, 100, 150, 200]
    assert parts.export_latest(cfg("vm5"), store) == OK
    for name in ("lora-pas-200", "base-meme-chaine"):
        export_gguf.verify_export(store / "modeles" / name)


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
        parts.train_part(cfg("vm1", kill_at=38), store, 1)
    saved = _step(store)
    assert 37 - saved <= 10  # au plus 5 min perdues (30 s par pas simulé)
    seen.clear()
    assert parts.train_part(cfg("vm2"), store, 1) == OK
    assert seen == list(range(saved, 50))


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
        if step == 50:
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
    assert parts.train_part(cfg("vm1", nan_at=30), store, 1) == STOPPED
    last = parts.Store(store).latest()[1]["state"]
    assert last["step"] < 30 and math.isfinite(last["initial_loss"])


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
    assert parts.train_part(cfg("vm1", hot_at=12), store, 1) == STOPPED
    assert _step(store) == 12


def test_donnees_changees_refusees(env):
    cfg, store, train = env
    parts.prove(cfg(), store)
    _write(train, _rows(999))
    with pytest.raises(parts.Refused, match="différents"):
        parts.train_part(cfg(), store, 1)


@pytest.mark.parametrize("rows", [_rows(20, licence="interne client"), _rows(20, confidential=True)])
def test_rien_de_non_public_sur_colab(env, rows):
    cfg, store, train = env
    _write(train, rows)
    with pytest.raises(parts.Refused) as e:
        parts.prove(cfg(), store)
    assert e.value.code == parts.DATA_REFUSED


def test_export_rate_bloque_les_parties(env, monkeypatch):
    cfg, store, _ = env

    def boom(*_a, **_k):
        raise export_gguf.ExportError("LoRA adapters are no longer supported")

    monkeypatch.setattr(export_gguf, "export", boom)
    with pytest.raises(parts.Refused, match="export"):
        parts.prove(cfg(), store)
    with pytest.raises(parts.Refused, match="partie 0"):
        parts.train_part(cfg(), store, 1)


def test_invite_identique_a_ollama():
    # rendu relevé sur Ollama 0.40.16, qwen3:1.7b, think=false (_debug_render_only), le 22/11/2026
    assert render_prompt("SYSTEME", "QUESTION") == (
        "<|im_start|>system\n\nSYSTEME<|im_end|>\n<|im_start|>user\nQUESTION /no_think<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n")


def test_modelfile_sans_adapter_et_en_lf(tmp_path):
    text = export_gguf.modelfile_text('# commentaire\nFROM C:\\blob\nTEMPLATE """x"""\nLICENSE """long', "model.gguf")
    assert text.startswith("FROM ./model.gguf\n") and 'TEMPLATE """x"""' in text
    assert "ADAPTER" not in text and "blob" not in text and "long" not in text
    export_gguf.export(tmp_path, tmp_path / "o", simulate=True)
    assert b"\r\n" not in (tmp_path / "o" / "Modelfile").read_bytes()
