"""Registre de modèles contre un Ollama simulé : lecture, test, activation, retour arrière, traçabilité."""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.domain.workflow import CurrentUser
from app.llm import OllamaProvider
from app.main import create_app
from app.models_registry import RegistryError, RegistryService
from app.models_registry.__main__ import main as cli
from app.models_registry.store import RegistryStore, active_model_resolver

from . import fake_engine


@pytest.fixture
def engine():
    srv, url = fake_engine.start()
    yield url
    srv.shutdown()


@pytest.fixture
def settings(engine, tmp_path):
    return Settings(ollama_base_url=engine, llm_provider="ollama", ollama_generation_model="qwen-good:4b",
                    ollama_embedding_model="bge-m3:latest", auth_mode="dev",
                    models_registry_path=str(tmp_path / "models.json"))


@pytest.fixture
def svc(settings):
    return RegistryService(settings)


def calls(*paths):
    return [c for c in fake_engine.FakeEngine.paths if c[1] in paths]


# --- lecture ---------------------------------------------------------------------------------------
def test_list_reads_card_and_never_writes(svc):
    data = svc.list()
    card = next(m for m in data["models"] if m["name"] == "qwen-good:4b")
    assert card["max_context"] == 262144 and card["quantization"] == "Q4_K_M"
    assert card["capabilities"] == ["completion", "tools"] and card["license"] == "Apache License"
    assert card["size_bytes"] == 2_500_000_000 and card["active"] is True
    assert data["limits"]["engine"]["allocated_context"] == 4096          # ≠ 262 144 : le moteur alloue moins
    assert data["limits"]["model"]["max_context"] == 262144
    assert data["limits"]["engine"]["loaded_context"] == 4096 and data["limits"]["app"]["max_upload_mb"] == 25
    paths = {c[1] for c in fake_engine.FakeEngine.paths}
    assert paths <= {"/api/tags", "/api/show", "/api/ps"}                  # lecture seule, jamais de chat/pull


def test_embedding_model_is_labelled(svc):
    roles = {m["name"]: m["role"] for m in svc.list()["models"]}
    assert roles["bge-m3:latest"] == "embedding" and roles["qwen-good:4b"] == "generation"


def test_engine_down_is_reported(settings):
    s = settings.model_copy(update={"ollama_base_url": "http://127.0.0.1:9"})
    assert RegistryService(s).list()["engine"]["reachable"] is False


def test_non_local_engine_is_refused(settings):
    s = settings.model_copy(update={"ollama_base_url": "http://exemple.invalid:11434"})
    with pytest.raises(RegistryError) as e:
        RegistryService(s)
    assert e.value.code == "ENGINE_HOST_REFUSED"


# --- test automatique ------------------------------------------------------------------------------
def keys(report, status):
    return {c["key"] for c in report["checks"] if c["status"] == status}


def test_good_model_passes_all_checks(svc):
    r = svc.test("qwen-good:4b")
    assert r["passed"] and not keys(r, "fail") and r["tokens_per_second"] == 40.0   # eval_count / eval_duration, pas la durée totale (8 s)
    assert {c["key"] for c in r["checks"]} == {"capabilities", "context", "json", "french", "citation",
                                               "refusal", "speed"}


@pytest.mark.parametrize("name, failing", [
    ("bad-english:1b", "french"), ("no-refusal:2b", "refusal"),
    ("bad-citation:2b", "citation"), ("broken-json:2b", "json"),
    ("bge-m3:latest", "capabilities")])
def test_bad_models_fail_the_right_check(svc, name, failing):
    r = svc.test(name)
    assert not r["passed"] and failing in keys(r, "fail")


def test_unmeasurable_speed_is_a_warning_not_a_failure(settings):
    fake_engine.FakeEngine.tps = 0
    r = RegistryService(settings).test("qwen-good:4b")
    assert "speed" in keys(r, "warn") and r["passed"]


def test_small_allocated_context_fails(settings):
    s = settings.model_copy(update={"ollama_num_ctx": 1024})
    assert "context" in keys(RegistryService(s).test("qwen-good:4b"), "fail")


def test_unknown_model_is_404(svc):
    with pytest.raises(RegistryError) as e:
        svc.test("absent:1b")
    assert e.value.status == 404


# --- activation, retour arrière ------------------------------------------------------------------------
def test_activation_requires_a_passing_test(svc):
    with pytest.raises(RegistryError) as e:
        svc.activate("no-refusal:2b")
    assert e.value.code == "TEST_REQUIRED"
    svc.test("no-refusal:2b")   # test en échec : toujours refusé
    with pytest.raises(RegistryError):
        svc.activate("no-refusal:2b")


def test_activate_then_rollback_with_history(svc, settings):
    svc.test("bad-english:1b")  # échec
    fake_engine.FakeEngine.models["alt:3b"] = {"caps": ["completion"], "ctx": 32768, "quant": "Q5_K_M"}
    assert svc.test("alt:3b")["passed"]
    res = svc.activate("alt:3b", by="usr_1")
    assert res["active"] == "alt:3b" and res["previous"] == "qwen-good:4b"
    assert svc.current() == "alt:3b"
    hist = RegistryStore(settings.models_registry_path).load()["history"]
    assert [h["action"] for h in hist] == ["initial", "activate"]
    back = svc.rollback(by="usr_1")
    assert back["active"] == "qwen-good:4b" and svc.current() == "qwen-good:4b"
    assert svc.list()["previous"] == "alt:3b"


def test_rollback_without_history_is_refused(svc):
    with pytest.raises(RegistryError) as e:
        svc.rollback()
    assert e.value.code == "NO_PREVIOUS_MODEL"


def test_test_is_invalidated_when_the_model_changes(svc):
    fake_engine.FakeEngine.models["alt:3b"] = {"caps": ["completion"], "ctx": 32768, "quant": "Q5_K_M"}
    svc.test("alt:3b")
    # le condensat change (modèle remplacé dans le moteur) : l'ancien test ne vaut plus
    svc.store.record_test("alt:3b", {**svc.store.last_test("alt:3b"), "digest": "autre"})
    with pytest.raises(RegistryError) as e:
        svc.activate("alt:3b")
    assert e.value.code == "TEST_REQUIRED"


def test_embedding_change_is_refused_with_reindex_message(svc):
    for kwargs in ({"role": "embedding"}, {}):
        with pytest.raises(RegistryError) as e:
            svc.activate("bge-m3:latest", **kwargs)
        assert "réindexation requise" in e.value.message and e.value.code == "REINDEX_REQUIRED"


# --- persistance ---------------------------------------------------------------------------------------
def test_store_is_atomic_and_survives_corruption(tmp_path):
    store = RegistryStore(tmp_path / "sub" / "models.json")
    store.set_active("a", by="u", action="activate", base="b")
    assert json.loads(store.path.read_text(encoding="utf-8"))["active"] == "a"
    assert [p.name for p in store.path.parent.iterdir()] == ["models.json"]   # aucun fichier temporaire
    store.path.write_text("{pas du json", encoding="utf-8")
    assert store.load()["active"] is None and store.path.with_suffix(".corrupt").exists()


def test_registry_file_is_ignored_by_git():
    import subprocess
    out = subprocess.run(["git", "check-ignore", "backend/data/models.json"], capture_output=True, check=False,
                         text=True, cwd=__file__.rsplit("backend", 1)[0])
    assert out.returncode == 0


# --- prise en compte sans redémarrage, et traçabilité --------------------------------------------------
def test_next_generation_uses_active_model_without_restart(svc, settings):
    from pydantic import BaseModel

    class Out(BaseModel):
        status: str = "ok"

    provider = OllamaProvider(settings.ollama_base_url, settings.ollama_generation_model,
                              settings.ollama_embedding_model, settings.allowed_hosts,
                              model_resolver=active_model_resolver(settings))
    assert provider.name == "ollama:qwen-good:4b"
    fake_engine.FakeEngine.models["alt:3b"] = {"caps": ["completion"], "ctx": 32768, "quant": "Q5_K_M"}
    svc.test("alt:3b")
    svc.activate("alt:3b")
    assert provider.name == "ollama:alt:3b"                  # nom exact, tracé dans record_run
    fake_engine.FakeEngine.paths.clear()
    provider.generate_structured("x", Out)
    assert next(c for c in fake_engine.FakeEngine.paths if c[1] == "/api/chat")[2] == "alt:3b"
    svc.rollback()
    assert provider.name == "ollama:qwen-good:4b"


def test_run_records_exact_model_name(repo, settings, svc):
    from app.services.generation import record_run

    fake_engine.FakeEngine.models["alt:3b"] = {"caps": ["completion"], "ctx": 32768, "quant": "Q5_K_M"}
    svc.test("alt:3b")
    svc.activate("alt:3b")
    provider = OllamaProvider(settings.ollama_base_url, settings.ollama_generation_model,
                              settings.ollama_embedding_model, settings.allowed_hosts,
                              model_resolver=active_model_resolver(settings))
    did = repo.create_dossier("D", "C", "fr", "usr_dev")
    rid = record_run(repo, provider, dossier_id=did, kind="section", prompt="p", status="ok",
                     attempts=1, latency_ms=1)
    from sqlalchemy import select

    from app.storage import schema as s
    with repo.engine.connect() as c:
        row = c.execute(select(s.generation_runs).where(s.generation_runs.c.id == rid)).first()
    assert row.provider == "ollama:alt:3b"


# --- budget de contexte ----------------------------------------------------------------------------------
def test_context_budget_adds_up_and_reports_unsent(svc):
    b = svc.context(candidate_tokens=10_000)
    assert b["window_allocated"] == 4096 and b["window_max"] == 262144
    assert b["system"] + b["context"] + b["passages"] + b["response_reserved"] + b["free"] == 4096
    assert b["passages_unsent"] == 10_000 - b["passages"] > 0 and b["passages_unsent_count"] > 0
    small = svc.context(candidate_tokens=100)
    assert small["passages"] == 100 and small["passages_unsent"] == 0


# --- API ------------------------------------------------------------------------------------------------
@pytest.fixture
def api(settings, repo, provider, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", settings.ollama_base_url)
    monkeypatch.setenv("OLLAMA_GENERATION_MODEL", "qwen-good:4b")
    monkeypatch.setenv("MODELS_REGISTRY_PATH", settings.models_registry_path)
    get_settings.cache_clear()
    app = create_app(provider, repo)
    with TestClient(app) as c:
        c.app_ = app
        yield c
    get_settings.cache_clear()


def test_api_flow_is_audited(api, repo):
    from app.workflow.versions import list_audit

    assert api.get("/api/v1/admin/models").json()["active"] == "qwen-good:4b"
    fake_engine.FakeEngine.models["alt:3b"] = {"caps": ["completion"], "ctx": 32768, "quant": "Q5_K_M"}
    r = api.post("/api/v1/admin/models/activate", json={"model": "alt:3b"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "TEST_REQUIRED"
    assert api.post("/api/v1/admin/models/test", json={"model": "alt:3b"}).json()["passed"] is True
    r = api.post("/api/v1/admin/models/activate", json={"model": "alt:3b"})
    assert r.status_code == 200 and r.json()["active"] == "alt:3b"
    r = api.post("/api/v1/admin/models/rollback")
    assert r.json()["active"] == "qwen-good:4b"
    actions = [(a["action"], a["object_id"]) for a in list_audit(repo) if a["object_type"] == "model"]
    assert actions == [("model.activate", "alt:3b"), ("model.rollback", "qwen-good:4b")]
    ctx = api.get("/api/v1/admin/models/context?candidate_tokens=5000").json()
    assert ctx["passages_unsent"] > 0


def test_api_refuses_embedding_change(api):
    r = api.post("/api/v1/admin/models/activate", json={"model": "bge-m3:latest", "role": "embedding"})
    assert r.status_code == 409 and "réindexation requise" in r.json()["error"]["message"]


@pytest.mark.parametrize("role", ["consultant", "reviewer"])
def test_api_is_admin_only(api, role):
    from app.api.deps import get_current_user
    api.app_.dependency_overrides[get_current_user] = lambda: CurrentUser(id="u", role=role)
    for method, url, body in [("get", "/api/v1/admin/models", None), ("get", "/api/v1/admin/models/context", None),
                              ("post", "/api/v1/admin/models/test", {"model": "qwen-good:4b"}),
                              ("post", "/api/v1/admin/models/activate", {"model": "qwen-good:4b"}),
                              ("post", "/api/v1/admin/models/rollback", None)]:
        r = getattr(api, method)(url, **({"json": body} if body else {}))
        assert r.status_code == 403, url


# --- ligne de commande -----------------------------------------------------------------------------------
def test_cli_list_test_activate_rollback(settings, monkeypatch, capsys):
    monkeypatch.setattr("app.models_registry.__main__.get_settings", lambda: settings)
    monkeypatch.setattr("app.models_registry.__main__._audit", lambda *a, **k: None)
    fake_engine.FakeEngine.models["alt:3b"] = {"caps": ["completion"], "ctx": 32768, "quant": "Q5_K_M"}
    assert cli(["list"]) == 0 and "qwen-good:4b" in capsys.readouterr().out
    assert cli(["activate", "alt:3b"]) == 2 and "TEST_REQUIRED" in capsys.readouterr().err
    assert cli(["test", "alt:3b"]) == 0 and "RÉUSSI" in capsys.readouterr().out
    assert cli(["activate", "alt:3b"]) == 0
    assert cli(["rollback"]) == 0 and "qwen-good:4b" in capsys.readouterr().out
    assert cli(["test", "bad-english:1b"]) == 1


# --- traçabilité figée par opération, étiquette des vecteurs, débit --------------------------------------
def test_logged_model_is_the_one_actually_sent_even_if_active_changes_mid_call(repo, settings):
    from sqlalchemy import select

    from app.services.generation import record_run
    from app.storage import schema as s

    fake_engine.FakeEngine.models["a:1"] = {"caps": ["completion"], "ctx": 8192, "quant": "Q4_0"}
    fake_engine.FakeEngine.models["b:2"] = {"caps": ["completion"], "ctx": 8192, "quant": "Q4_0"}
    chosen = ["a:1"]
    provider = OllamaProvider(settings.ollama_base_url, "a:1", "bge-m3:latest", settings.allowed_hosts,
                              model_resolver=lambda: chosen[0])
    from app.generation.llm_schemas import LLMSection
    provider.generate_structured("Clôture mensuelle", LLMSection)
    chosen[0] = "b:2"                                   # activation PENDANT l'opération (après l'envoi)
    assert provider.name == "ollama:b:2" and provider.served_model == "ollama:a:1"
    did = repo.create_dossier("D", "C", "fr", "usr_dev")
    rid = record_run(repo, provider, dossier_id=did, kind="section", prompt="p", status="ok",
                     attempts=1, latency_ms=1)
    with repo.engine.connect() as c:
        row = c.execute(select(s.generation_runs).where(s.generation_runs.c.id == rid)).first()
    assert row.provider == "ollama:a:1" and row.model == "ollama:a:1"


def test_vectors_are_labelled_with_the_embedding_model(settings, svc):
    provider = OllamaProvider(settings.ollama_base_url, "qwen-good:4b", "bge-m3:latest",
                              settings.allowed_hosts, model_resolver=active_model_resolver(settings))
    fake_engine.FakeEngine.models["alt:3b"] = {"caps": ["completion"], "ctx": 32768, "quant": "Q5_K_M"}
    svc.test("alt:3b")
    svc.activate("alt:3b")
    assert provider.name == "ollama:alt:3b" and provider.embedding_name == "ollama:bge-m3:latest"


def test_ingestion_stores_embedding_model_label(repo, settings, svc, monkeypatch, tmp_path):
    from app.domain.workflow import CurrentUser
    from app.services import ingestion

    class P(OllamaProvider):
        def embed(self, texts):
            return [[0.0] * 64 for _ in texts]

    provider = P(settings.ollama_base_url, "qwen-good:4b", "bge-m3:latest", settings.allowed_hosts)
    seen = {}
    monkeypatch.setattr(repo, "add_chunks", lambda chunks, vecs, model: seen.setdefault("m", model))
    did = repo.create_dossier("D", "C", "fr", "usr_dev")
    st = settings.model_copy(update={"upload_dir": str(tmp_path)})
    ingestion.ingest(repo, provider, did, "a.txt", "Un texte assez long sur la clôture.".encode(),
                     CurrentUser(id="usr_dev", role="admin"), settings=st)
    assert seen["m"] == "ollama:bge-m3:latest"


# --- mode démonstration (fournisseur fake ou demo) -------------------------------------------------------
@pytest.mark.parametrize("provider_name", ["fake", "demo"])
def test_api_refuses_test_activate_rollback_in_demo_mode(api, monkeypatch, provider_name):
    monkeypatch.setenv("LLM_PROVIDER", provider_name)
    get_settings.cache_clear()
    overview = api.get("/api/v1/admin/models").json()
    assert overview["engine"]["demo"] is True
    for url, body in [("/api/v1/admin/models/test", {"model": "qwen-good:4b"}),
                      ("/api/v1/admin/models/activate", {"model": "qwen-good:4b"}),
                      ("/api/v1/admin/models/rollback", None)]:
        r = api.post(url, **({"json": body} if body else {}))
        assert r.status_code == 409 and r.json()["error"]["code"] == "DEMO_MODE", url
    assert RegistryStore(get_settings().models_registry_path).active() is None   # rien n'a été écrit


def test_overview_is_not_demo_with_ollama(api):
    assert api.get("/api/v1/admin/models").json()["engine"]["demo"] is False
