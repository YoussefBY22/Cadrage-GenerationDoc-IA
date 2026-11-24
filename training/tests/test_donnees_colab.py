"""Paquet de données Colab (v2 relu + v3), carnet et import Ollama : tout est vérifié sans GPU ni réseau.

Le paquet `training/colab/cadrage-donnees-publiques.zip` est dans le dépôt (documents publics seulement) :
ces tests s'exécutent donc toujours, sans fichier à part.
"""

import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.generation import prompting
from app.generation.llm_schemas import LLMFindings, LLMSection
from app.generation.template_loader import load_template

from training import export_gguf, import_ollama
from training.dataset import assemble, v3_build
from training.train_lora import load_profile, render_prompt

COLAB = Path(__file__).resolve().parents[1] / "colab"
ZIP = COLAB / "cadrage-donnees-publiques.zip"
NOTEBOOK = COLAB / "cadrage_entrainement.ipynb"


def _read(name: str) -> list[dict]:
    with zipfile.ZipFile(ZIP) as z:
        return [json.loads(x) for x in z.read(name).decode("utf-8").splitlines() if x.strip()]


@pytest.fixture(scope="module")
def rows() -> dict[str, list[dict]]:
    return {p: _read(f"{p}.jsonl") for p in ("train", "val", "test")}


def _all(rows):
    return [r for part in rows.values() for r in part]


# ---------------------------------------------------------------- effectifs et séparation par document
def test_effectifs(rows):
    # v5 = v4 (341 / 25 / 169) + tâche « axes » (100 / 4 / 36), même découpage par rapport
    assert {p: len(v) for p, v in rows.items()} == {"train": 441, "val": 29, "test": 205}
    lots = Counter(r["meta"]["lot"] for r in _all(rows))
    assert lots == {"eca-2023-2026": 622, "pilote-v2": 28, "pilote-v3": 25}
    axes = Counter(r["meta"]["split"] for r in _all(rows) if r["meta"]["task_type"] == "axes")
    assert axes == {"train": 100, "val": 4, "test": 36}
    assert {r["meta"]["split"] for r in rows["train"]} == {"train"}


def test_le_test_est_dur_et_assez_grand(rows):
    tasks = Counter(r["meta"]["task_type"] for r in rows["test"])
    assert len(rows["test"]) >= 60 and tasks["conflit"] >= 15 and tasks["refus"] >= 10
    assert {"extraction", "position", "conflit", "feuille_de_route", "refus"} <= set(tasks)
    labels = Counter(r["meta"]["etiquette"] for r in rows["test"] if r["meta"].get("etiquette"))
    assert {"accept", "partial", "reject", "conflict", "aligned"} <= set(labels)


def test_chaque_exemple_a_un_type_de_tache(rows):
    assert all(r["meta"].get("task_type") for r in _all(rows))
    assert len(rows["train"]) >= 300


def test_aucun_document_des_deux_cotes(rows):
    docs = {p: {r["meta"]["source"] for r in v} for p, v in rows.items()}
    assert not (docs["train"] & docs["val"]) and not (docs["train"] & docs["test"]) and not (docs["val"] & docs["test"])
    assert assemble.check(_all(rows)) == []


def test_aucune_phrase_ni_passage_commun_entre_entrainement_et_test(rows):
    def texts(part):
        return {p["texte"] for r in rows[part] for p in r["meta"]["rendu"]["passages"]}

    for other in ("val", "test"):
        assert not (texts("train") & texts(other))


def test_tous_les_types_en_test(rows):
    kinds = {r["meta"]["kind"] for r in rows["test"]}
    assert {"feuille de route", "extraction de constats", "refus", "conflit avec une contrainte",
            "position sur une recommandation"} <= kinds


# ---------------------------------------------------------------- licence, public seulement
def test_licence_ouverte_et_preuve_sur_chaque_exemple(rows):
    for r in _all(rows):
        m = r["meta"]
        assert m["licence"].startswith(assemble.OPEN) and m["licence_preuve"].startswith("https://")
        assert m["valide_par_humain"] is False and m["real"] is True and not m.get("confidential")


def test_le_paquet_ne_contient_que_du_public(rows):
    with zipfile.ZipFile(ZIP) as z:
        manifest = json.loads(z.read("MANIFEST.json"))
        assert sorted(z.namelist()) == ["MANIFEST.json", "test.jsonl", "train.jsonl", "val.jsonl"]
        for name, sha in manifest["sha256"].items():
            assert hashlib.sha256(z.read(name)).hexdigest() == sha
    assert "aucun document client" in manifest["contenu"]
    assert all(d["licence"].startswith(assemble.OPEN) for d in manifest["documents"].values())
    assert manifest["effectifs"]["total"] == 675
    assert len(manifest["rapports_cour"]) >= 90 and all(r["url"].startswith("https://www.eca.europa.eu/") for r in manifest["rapports_cour"])


# ---------------------------------------------------------------- invites identiques à l'application d'aujourd'hui
def test_chaque_invite_est_celle_que_l_application_envoie_aujourd_hui(rows):
    for r in _all(rows):
        assert r["messages"][0]["content"] == prompting.system_prompt("fr")
        assert v3_build.rerender(r) == r["messages"][1]["content"], r["meta"]["id"]
        assert [m["role"] for m in r["messages"]] == ["system", "user", "assistant"]


def test_les_consignes_de_gabarit_sont_celles_des_gabarits_actuels(rows):
    checked = 0
    for r in _all(rows):
        origin = r["meta"]["rendu"]["spec_origine"]
        if not origin.startswith("gabarit:"):
            continue
        kind, key = origin.removeprefix("gabarit:").split("/")
        section = next(s for s in load_template(kind, "fr").sections if s.key == key)
        assert r["meta"]["rendu"]["spec"] == section.model_dump(), r["meta"]["id"]
        checked += 1
    assert checked >= 15


def test_les_constats_utilisent_la_tache_constats_de_l_application(rows):
    findings = [r for r in _all(rows) if r["meta"]["rendu"]["tache"] == "constats"]
    assert len(findings) >= 100
    for r in findings:
        assert r["messages"][1]["content"].startswith(prompting._t("fr")["task_findings"])
        LLMFindings.model_validate(json.loads(r["messages"][2]["content"]))


def test_chaque_exemple_passe_le_verificateur_de_l_application(rows):
    from training.dataset import eca_axes
    for r in _all(rows):
        if r["meta"]["task_type"] == "axes":  # pas de phrase à vérifier : contrôle propre à la tâche
            assert eca_axes.check(r) == [], r["meta"]["id"]
            continue
        tpv, blocking = v3_build.verify_example(r)
        assert blocking == [] and tpv == 1.0, r["meta"]["id"]


def test_les_refus_sont_gardes_et_bien_formes(rows):
    refus = [r for r in _all(rows) if json.loads(r["messages"][2]["content"]).get("status") == "insufficient_evidence"]
    assert len(refus) >= 8
    for r in refus:
        out = LLMSection.model_validate(json.loads(r["messages"][2]["content"]))
        assert out.sentences == [] and out.missing_evidence


def test_les_nuances_des_sources_sont_gardees(rows):
    text = "\n".join(r["messages"][2]["content"] for r in _all(rows))
    for nuance in ("parfois", "pourraient", "risque d", "accepte partiellement"):
        assert nuance in text


def test_les_exemples_tiennent_dans_la_fenetre_d_entrainement(rows):
    limit = load_profile("colab-parties")["max_seq_len"]
    for r in _all(rows):
        full = render_prompt(r["messages"][0]["content"], r["messages"][1]["content"]) + r["messages"][2]["content"]
        assert prompting.estimate_tokens(full) < limit, r["meta"]["id"]


# ---------------------------------------------------------------- carnet Colab
@pytest.fixture(scope="module")
def notebook() -> dict:
    return json.loads(NOTEBOOK.read_text("utf-8"))


def _src(cell) -> str:
    return "".join(cell["source"])


def test_carnet_verifie_l_empreinte_du_paquet(notebook):
    code = "\n".join(_src(c) for c in notebook["cells"] if c["cell_type"] == "code")
    sha = hashlib.sha256(ZIP.read_bytes()).hexdigest()
    assert f'DONNEES = "{sha}"' in code
    assert re.search(r'CODE = "[0-9a-f]{40}"', code) and re.search(r'LLAMA = "[0-9a-f]{40}"', code)
    assert "hashlib.sha256(contenu).hexdigest() != DONNEES" in code


def test_carnet_pin_base_revision_et_ollama(notebook):
    code = "\n".join(_src(c) for c in notebook["cells"] if c["cell_type"] == "code")
    p = load_profile("colab-parties")
    assert f'BASE_REVISION = "{p["base_revision"]}"' in code and 'd("Qwen/Qwen3-4B", revision=' in code
    assert 'OLLAMA = "0.40.17"' in code and "ollama pull qwen3:4b" in code
    assert "Qwen3-1.7B" not in code and "qwen3:1.7b" not in code


def test_carnet_une_cellule_par_etape_avec_titre_et_duree(notebook):
    titles = [re.search(r"#@title (.*?) \{display-mode", _src(c)).group(1)
              for c in notebook["cells"] if c["cell_type"] == "code"]
    assert len(titles) == 16
    for t in titles:
        assert re.search(r"\d", t) or "instantané" in t, t
    steps = [t for t in titles if t.startswith("Étape")]
    assert len(steps) == 7 and titles[7].startswith("Partie 0")
    assert any("Exporter le modèle entraîné" in t for t in titles) and any("MÊME chaîne" in t for t in titles)
    assert titles[-2].startswith("Résumé") and titles[-1].startswith("Test avant téléchargement")


def test_carnet_sans_secret_ni_chemin_personnel(notebook):
    text = "\n".join(_src(c) for c in notebook["cells"])
    assert not re.search(r"hf_[A-Za-z0-9]{10,}|ghp_|HF_TOKEN|api[_-]?key|password|mot de passe :", text, re.IGNORECASE)
    assert not re.search(r"[A-Za-z]:\\|/Users/|/home/", text)
    assert "drive.mount" in text and "files.upload" not in text  # l'utilisateur monte son Drive, rien d'envoyé à la main


def test_carnet_enchaine_les_bonnes_actions(notebook):
    code = "\n".join(_src(c) for c in notebook["cells"] if c["cell_type"] == "code")
    for action in ('cadrage("preuve")', 'cadrage("partie", 1)', 'cadrage("partie", 2)', 'cadrage("partie", 3)', 'cadrage("etat")',
                   'cadrage("exporter")', 'cadrage("exporter-base")', 'cadrage("resume")'):
        assert action in code
    assert "task_type" in code and "LLMStance" in code and "etiquette_juste" in code  # test par tâche, position notée
    assert "build_quantize" in code and "check_template" in code and "cadrage-4b-lora" in code


# ---------------------------------------------------------------- import côté PC
def _folder(tmp_path, name, payload=b"GGUF-contenu"):
    d = tmp_path / name
    d.mkdir()
    (d / "model.gguf").write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()
    (d / "model.gguf.sha256").write_text(f"{sha}  model.gguf\n", encoding="utf-8")
    return d, sha


@pytest.fixture
def fake_ollama(monkeypatch):
    state = SimpleNamespace(calls=[], shas={}, bad_template=None)

    def run(cmd, what, cwd=None):
        state.calls.append((cmd, cwd))
        if cmd[:2] == ["ollama", "show"]:
            tag = cmd[-1]
            sha = state.shas.get(tag, "0" * 64)
            body = export_gguf.base_modelfile_text() if tag != state.bad_template else 'TEMPLATE """autre"""\n'
            return f"FROM /blobs/sha256-{sha}\n{body}"
        return ""

    monkeypatch.setattr(export_gguf, "_run", run)
    monkeypatch.setattr(export_gguf, "post", lambda path, body: {"eval_count": 3, "message": {"content": "ok"}})
    return state


def test_import_verifie_cree_et_repond(tmp_path, fake_ollama):
    lora, sha = _folder(tmp_path, "cadrage-4b-lora", b"GGUF-lora")
    base, sha_b = _folder(tmp_path, "cadrage-4b-base", b"GGUF-base")
    sums = tmp_path / "SHA256SUMS.txt"
    sums.write_text(f"{sha}  cadrage-4b-lora/model.gguf\n{sha_b}  cadrage-4b-base/model.gguf\n", encoding="utf-8")
    fake_ollama.shas = {"cadrage-4b-lora": sha, "cadrage-4b-base": sha_b}
    for kind, folder in (("base", base), ("lora", lora)):
        assert import_ollama.import_one(kind, folder, sums, say=lambda *_: None) == "ok"
    creates = [c for c, _ in fake_ollama.calls if c[:2] == ["ollama", "create"]]
    assert [c[2] for c in creates] == ["cadrage-4b-base", "cadrage-4b-lora"]
    modelfile = (lora / "Modelfile").read_bytes()
    assert b"\r\n" not in modelfile and modelfile.startswith(b"FROM ./model.gguf\n")
    assert b"PARAMETER temperature 0.6" in modelfile


def test_import_refuse_un_fichier_abime(tmp_path, fake_ollama):
    d, _ = _folder(tmp_path, "cadrage-4b-lora")
    (d / "model.gguf").write_bytes(b"GGUF-tronque")
    with pytest.raises(export_gguf.ExportError, match="SHA-256 différent"):
        import_ollama.import_one("lora", d, say=lambda *_: None)
    assert not any(c[:2] == ["ollama", "create"] for c, _ in fake_ollama.calls)


def test_import_refuse_si_sha256sums_dit_autre_chose(tmp_path, fake_ollama):
    d, _ = _folder(tmp_path, "cadrage-4b-lora")
    sums = tmp_path / "SHA256SUMS.txt"
    sums.write_text(f"{'1' * 64}  cadrage-4b-lora/model.gguf\n", encoding="utf-8")
    with pytest.raises(export_gguf.ExportError, match="SHA256SUMS"):
        import_ollama.import_one("lora", d, sums, say=lambda *_: None)


def test_import_refuse_un_fichier_qui_n_est_pas_un_gguf(tmp_path, fake_ollama):
    d, _ = _folder(tmp_path, "cadrage-4b-base", b"PAS-UN-GGUF")
    with pytest.raises(export_gguf.ExportError, match="GGUF"):
        import_ollama.import_one("base", d, say=lambda *_: None)


def test_import_refuse_si_ollama_n_a_pas_le_meme_fichier(tmp_path, fake_ollama):
    d, _ = _folder(tmp_path, "cadrage-4b-lora")  # fake_ollama.shas vide : Ollama rapporte une autre empreinte
    with pytest.raises(export_gguf.ExportError, match="empreinte"):
        import_ollama.import_one("lora", d, say=lambda *_: None)


def test_import_refuse_si_le_gabarit_d_ollama_a_change(tmp_path, fake_ollama):
    d, _ = _folder(tmp_path, "cadrage-4b-lora")
    fake_ollama.bad_template = "qwen3:4b"
    with pytest.raises(export_gguf.ExportError, match="diffère"):
        import_ollama.import_one("lora", d, say=lambda *_: None)


# ---------------------------------------------------------------- carnet Kaggle (même contenu, stockage /kaggle/working)
KAGGLE = Path(__file__).resolve().parents[1] / "kaggle" / "cadrage_entrainement_kaggle.ipynb"


def test_carnet_kaggle_meme_chaine_que_colab_sans_drive_ni_secret():
    kg, colab = json.loads(KAGGLE.read_text("utf-8")), json.loads(NOTEBOOK.read_text("utf-8"))
    text = "\n".join(_src(c) for c in kg["cells"])
    for const in ("CODE = ", "DONNEES = ", "LLAMA = ", "OLLAMA = ", "BASE_REVISION = "):
        line = lambda nb: next(ln for c in nb["cells"] for ln in _src(c).split("\n") if ln.startswith(const))  # noqa: E731
        assert line(kg).split("#")[0].strip() == line(colab).split("#")[0].strip()  # mêmes versions épinglées
    assert "/kaggle/working/cadrage-entrainement" in text and "CUDA_VISIBLE_DEVICES" in text
    assert "drive.mount" not in text and "google.colab" not in text and "/content" not in text
    assert 'cadrage("partie", 3)' in text and "task_type" in text and "etiquette_juste" in text
    assert "Quick Save" in text and "Internet" in text and "Persistence" in text and "Save & Run All" in text
    assert not re.search(r"hf_[A-Za-z0-9]{10,}|ghp_|HF_TOKEN|api[_-]?key|password|mot de passe :", text, re.IGNORECASE)
    assert len([c for c in kg["cells"] if c["cell_type"] == "code"]) == 16
