"""Livraison hors ligne : vérifications statiques (sans Docker démarré, sans réseau)."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "docker-compose.yml"
SH_SCRIPTS = sorted((ROOT / "deploy").rglob("*.sh"))
PS_SCRIPTS = sorted((ROOT / "deploy").rglob("*.ps1"))
ENV = {"POSTGRES_DB": "t", "POSTGRES_USER": "t", "POSTGRES_PASSWORD": "t"}


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_compose_is_valid_yaml_with_expected_services(compose):
    assert {"db", "api", "frontend", "proxy", "ollama"} <= set(compose["services"])
    assert compose["networks"]["internal"]["internal"] is True


def test_db_has_no_published_port_and_only_internal_network(compose):
    db = compose["services"]["db"]
    assert "ports" not in db and db["networks"] == ["internal"]


def test_only_proxy_is_on_edge_and_api_cannot_reach_internet(compose):
    on_edge = [n for n, s in compose["services"].items() if "edge" in s.get("networks", [])]
    assert on_edge == ["proxy"]
    for name in ("api", "db", "frontend", "ollama"):
        assert compose["services"][name]["networks"] == ["internal"], name
    for name, svc in compose["services"].items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), (name, port)


def test_ollama_is_optional_profile(compose):
    assert compose["services"]["ollama"]["profiles"] == ["llm"]


def test_api_runs_in_token_mode(compose):
    assert compose["services"]["api"]["environment"]["AUTH_MODE"] == "token"


def test_no_clear_secret_in_compose(compose):
    for name, svc in compose["services"].items():
        for key, value in (svc.get("environment") or {}).items():
            if re.search(r"PASS|SECRET|TOKEN|KEY", key):
                assert str(value).startswith("${"), (name, key)
    text = COMPOSE.read_text(encoding="utf-8")
    assert not re.search(r"postgres(ql)?(\+\w+)?://\w+:(?!\$\{)\w+@", text)


def test_images_are_pinned(compose):
    for name, svc in compose["services"].items():
        tag = svc["image"].rpartition(":")[2]
        assert ":" in svc["image"] and tag not in ("latest", ""), (name, svc["image"])
        assert re.search(r"\d", tag), (name, tag)
    for df in (ROOT / "backend" / "Dockerfile", ROOT / "frontend" / "Dockerfile"):
        froms = re.findall(r"^FROM\s+(\S+)", df.read_text(encoding="utf-8"), re.MULTILINE)
        assert froms and all(":" in f and not f.endswith(":latest") for f in froms), df


def test_dockerfiles_run_as_non_root_and_without_external_url():
    for df in (ROOT / "backend" / "Dockerfile", ROOT / "frontend" / "Dockerfile"):
        text = df.read_text(encoding="utf-8")
        assert re.search(r"^USER\s+(?!root)\S+", text, re.MULTILINE), df
        assert "http://" not in text and "curl " not in text and "wget " not in text


def test_proxy_config_has_no_external_upstream():
    conf = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")
    hosts = set(re.findall(r"proxy_pass\s+https?://([\w.-]+)", conf))
    assert hosts == {"api", "frontend"}


@pytest.mark.parametrize("script", SH_SCRIPTS, ids=lambda p: p.name)
def test_shell_scripts_are_strict(script):
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text


@pytest.mark.parametrize("script", SH_SCRIPTS, ids=lambda p: p.name)
def test_shell_scripts_parse(script):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash absent")
    data = script.read_bytes().replace(b"\r\n", b"\n")
    r = subprocess.run([bash, "-n"], input=data, capture_output=True, check=False)
    assert r.returncode == 0, r.stderr.decode()


@pytest.mark.parametrize("script", PS_SCRIPTS, ids=lambda p: p.name)
def test_powershell_scripts_fail_fast(script):
    assert '$ErrorActionPreference = "Stop"' in script.read_text(encoding="utf-8")


def test_backup_and_restore_verify_checksums():
    assert "sha256sum" in (ROOT / "deploy" / "backup.sh").read_text(encoding="utf-8")
    restore = (ROOT / "deploy" / "restore.sh").read_text(encoding="utf-8")
    assert restore.index("sha256sum -c") < restore.index("pg_restore")   # vérifier AVANT d'écrire
    assert "--yes" in restore


def test_install_is_offline():
    text = (ROOT / "deploy" / "offline" / "install.sh").read_text(encoding="utf-8")
    assert "--no-build" in text and "--pull never" in text and "docker load" in text
    assert "pip install" not in text and "npm " not in text


def test_bundle_script_ships_every_deploy_file():
    text = (ROOT / "deploy" / "offline" / "build_bundle.sh").read_text(encoding="utf-8")
    for name in ("nginx.conf", "backup.sh", "restore.sh", "install.sh", "env.production.example"):
        assert name in text


def test_ci_has_frontend_and_training_jobs():
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    assert {"backend", "frontend", "training", "compose-config"} <= set(ci["jobs"])
    steps = " ".join(str(s.get("run", "")) for s in ci["jobs"]["frontend"]["steps"])
    # « npm install » : npm ci échoue sur un lockfile généré sous Windows (paquets optionnels Linux absents)
    assert "npm ci" in steps or "npm install" in steps
    assert all(w in steps for w in ("npm run lint", "npm test", "npm run build"))
    assert "pytest training/tests" in " ".join(
        str(s.get("run", "")) for s in ci["jobs"]["training"]["steps"])


@pytest.mark.parametrize("profile", [[], ["--profile", "llm"]])
def test_docker_compose_config(profile):
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("binaire docker absent")
    r = subprocess.run([docker, "compose", *profile, "config", "-q"], cwd=ROOT,
                       env={**os.environ, **ENV}, capture_output=True, text=True, check=False)
    if r.returncode != 0 and "compose" in r.stderr and "not a docker command" in r.stderr:
        pytest.skip("plugin compose absent")
    assert r.returncode == 0, r.stderr
