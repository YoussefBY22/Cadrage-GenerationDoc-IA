"""Ollama SIMULÉ (serveur HTTP local) : /api/tags, /api/show, /api/ps, /api/chat. Aucun vrai modèle."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

GOOD = {
    "ground": {"status": "ok", "sentences": [
        {"text": "Le délai de clôture est de douze jours ouvrés et les écarts sont corrigés par la "
                 "direction financière.", "kind": "fact", "sources": ["P1"]}]},
    "refuse": {"status": "insufficient_evidence", "sentences": [],
               "missing_evidence": "aucun passage ne traite ce sujet"},
}

MODELS = {
    "qwen-good:4b": {"caps": ["completion", "tools"], "ctx": 262144, "quant": "Q4_K_M"},
    "bad-english:1b": {"caps": ["completion"], "ctx": 8192, "quant": "Q8_0",
                       "ground": {"status": "ok", "sentences": [
                           {"text": "The closing delay is twelve days and the figures are fixed by the "
                                    "finance team of the company.", "kind": "fact", "sources": ["P1"]}]}},
    "no-refusal:2b": {"caps": ["completion"], "ctx": 8192, "quant": "Q4_0", "refuse": GOOD["ground"]},
    "bad-citation:2b": {"caps": ["completion"], "ctx": 8192, "quant": "Q4_0",
                        "ground": {"status": "ok", "sentences": [
                            {"text": "Le délai de clôture est de douze jours ouvrés et les écarts sont "
                                     "corrigés par la direction.", "kind": "fact", "sources": ["P9"]}]}},
    "broken-json:2b": {"caps": ["completion"], "ctx": 8192, "quant": "Q4_0", "raw": "ceci n'est pas du JSON"},
    "bge-m3:latest": {"caps": ["embedding"], "ctx": 8192, "quant": "F16"},
}


class FakeEngine(BaseHTTPRequestHandler):
    paths: ClassVar[list] = []   # (méthode, chemin) de chaque requête reçue
    models: ClassVar[dict] = {}
    tps: int = 40      # jetons de sortie par seconde simulés

    def log_message(self, *a):
        pass

    def _send(self, out, code=200):
        data = json.dumps(out).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        type(self).paths.append(("GET", self.path))
        if self.path == "/api/tags":
            return self._send({"models": [
                {"name": n, "model": n, "digest": f"sha-{n}", "size": 2_500_000_000,
                 "modified_at": "2026-11-20T10:00:00Z",
                 "details": {"family": "qwen3", "parameter_size": "4.0B", "quantization_level": m["quant"]}}
                for n, m in type(self).models.items()]})
        if self.path == "/api/ps":
            return self._send({"models": [{"name": "qwen-good:4b", "size_vram": 2_000_000_000,
                                           "context_length": 4096}]})
        self._send({}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).paths.append(("POST", self.path, body.get("model")))
        models = type(self).models
        if self.path == "/api/show":
            m = models.get(body.get("model"))
            if m is None:
                return self._send({"error": "not found"}, 404)
            return self._send({"license": "Apache License\nVersion 2.0", "capabilities": m["caps"],
                               "details": {"family": "qwen3", "parameter_size": "4.0B",
                                           "quantization_level": m["quant"]},
                               "model_info": {"general.architecture": "qwen3",
                                              "qwen3.context_length": m["ctx"]}})
        if self.path == "/api/chat":
            m = models.get(body.get("model"))
            if m is None:
                return self._send({"error": "not found"}, 404)
            prompt = body["messages"][-1]["content"]
            if m.get("raw"):
                content = m["raw"]
            elif "Architecture de sécurité" in prompt:
                content = json.dumps(m.get("refuse", GOOD["refuse"]))
            else:
                content = json.dumps(m.get("ground", GOOD["ground"]))
            return self._send({"message": {"role": "assistant", "content": content},
                               "eval_count": type(self).tps, "prompt_eval_count": 120,
                               "total_duration": 1_000_000_000})
        self._send({}, 404)


def start(models: dict | None = None, tps: int = 40):
    FakeEngine.paths = []
    FakeEngine.models = dict(MODELS if models is None else models)
    FakeEngine.tps = tps
    srv = HTTPServer(("127.0.0.1", 0), FakeEngine)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"
