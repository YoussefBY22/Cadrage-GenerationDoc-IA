"""NFR-01 / C1 : le produit n'ouvre aucune connexion sortante."""

import ast
import re
import socket
from pathlib import Path

import pytest

from .netguard import OutboundConnectionBlocked

APP_DIR = Path(__file__).resolve().parent.parent / "app"

# Bibliothèques qui n'ont pas leur place dans le produit (clients cloud, télémétrie, courriel…).
FORBIDDEN_IMPORTS = {
    "requests", "aiohttp", "urllib3", "http.client", "urllib.request", "ftplib", "smtplib",
    "telnetlib", "boto3", "botocore", "openai", "anthropic", "cohere", "google.generativeai",
    "sentry_sdk", "posthog", "mixpanel", "segment", "datadog", "opentelemetry", "newrelic",
}
LOCAL_URL = re.compile(
    r"https?://(localhost|127\.0\.0\.1|\[::1\]|ollama|host\.docker\.internal|testserver)\b")
ANY_URL = re.compile(r"https?://[^\s\"'<>)]+")


def scan_source(source: str, filename: str = "<src>") -> list[str]:
    """Retourne les violations trouvées dans un code Python."""
    problems = []
    for node in ast.walk(ast.parse(source, filename)):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        for name in names:
            if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS):
                problems.append(f"{filename}: import interdit {name!r}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for url in ANY_URL.findall(node.value):
                if not LOCAL_URL.match(url):
                    problems.append(f"{filename}: URL externe {url!r}")
    return problems


def test_dynamic_guard_blocks_external_connection():
    with pytest.raises(OutboundConnectionBlocked):
        socket.create_connection(("93.184.216.34", 80), timeout=1)


def test_dynamic_guard_blocks_dns():
    with pytest.raises(OutboundConnectionBlocked):
        socket.getaddrinfo("example.com", 443)


def test_dynamic_guard_allows_loopback():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    cli = socket.create_connection(srv.getsockname(), timeout=1)
    cli.close()
    srv.close()


def test_static_scan_detects_violations():
    """Le scanner lui-même doit détecter les fautes (sinon le test du dessous ne prouve rien)."""
    bad = "import requests\nfrom urllib import request\nX = 'https://api.openai.com/v1'\n"
    assert len(scan_source(bad)) >= 2
    assert scan_source("import json\nU = 'http://localhost:11434'\n") == []


def test_app_code_has_no_outbound_capability():
    problems = []
    for path in APP_DIR.rglob("*.py"):
        problems += scan_source(path.read_text(encoding="utf-8"), str(path))
    assert problems == []
