"""Contrat de OllamaProvider contre un serveur SIMULÉ local (aucun vrai modèle dans le cloud)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import pytest
from pydantic import BaseModel

from app.llm import LLMError, OllamaProvider

ALLOWED = {"localhost", "127.0.0.1"}


class Out(BaseModel):
    answer: str


class FakeOllama(BaseHTTPRequestHandler):
    requests: ClassVar[list] = []
    chat_content = json.dumps({"answer": "oui"})

    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append((self.path, body))
        if self.path == "/api/chat":
            out = {"message": {"role": "assistant", "content": type(self).chat_content}}
        elif self.path == "/api/embed":
            out = {"embeddings": [[0.1, 0.2, 0.3] for _ in body["input"]]}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def server():
    FakeOllama.requests = []
    FakeOllama.chat_content = json.dumps({"answer": "oui"})
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def make(url):
    return OllamaProvider(url, "gen-model", "emb-model", ALLOWED)


def test_generate_request_shape(server):
    text = make(server).generate("question", system="règles", temperature=0.0, seed=7,
                                 max_tokens=50)
    path, body = FakeOllama.requests[0]
    assert path == "/api/chat"
    assert body["model"] == "gen-model" and body["stream"] is False
    assert body["messages"][0] == {"role": "system", "content": "règles"}
    assert body["options"] == {"temperature": 0.0, "seed": 7, "num_predict": 50}
    assert body["think"] is False and body["keep_alive"] == "30m"
    assert text


def test_extra_options_and_think_flag(server):
    p = OllamaProvider(server, "g", "e", ALLOWED, think=True,
                       options={"num_ctx": 4096, "top_p": None, "top_k": 20})
    p.generate("q")
    _, body = FakeOllama.requests[0]
    assert body["think"] is True
    assert body["options"]["num_ctx"] == 4096 and body["options"]["top_k"] == 20
    assert "top_p" not in body["options"]


def test_embedding_prefixes_and_batching(server):
    p = OllamaProvider(server, "g", "e", ALLOWED, query_prefix="query: ",
                       passage_prefix="passage: ", embed_batch=2)
    assert len(p.embed(["a", "b", "c"])) == 3
    assert [b["input"] for _, b in FakeOllama.requests] == [["passage: a", "passage: b"],
                                                           ["passage: c"]]
    FakeOllama.requests.clear()
    p.embed_query(["x"])
    assert FakeOllama.requests[0][1]["input"] == ["query: x"]


def test_structured_sends_json_schema_and_validates(server):
    out = make(server).generate_structured("q", Out)
    _, body = FakeOllama.requests[0]
    assert body["format"] == Out.model_json_schema()
    assert out.answer == "oui"


def test_structured_invalid_output_raises(server):
    FakeOllama.chat_content = "pas du json"
    with pytest.raises(LLMError):
        make(server).generate_structured("q", Out)


def test_embed_and_dimension(server):
    p = make(server)
    assert p.embed(["a", "b"]) == [[0.1, 0.2, 0.3]] * 2
    assert p.embedding_dimension == 3


def test_http_error_becomes_llm_error(server):
    p = make(server)
    p.base_url += "/inexistant"
    with pytest.raises(LLMError):
        p.generate("q")


def test_remote_host_refused():
    with pytest.raises(LLMError, match="refusé"):
        OllamaProvider("http://api.example.com:11434", "m", "e", ALLOWED)


def test_missing_model_names_refused():
    with pytest.raises(LLMError):
        OllamaProvider("http://localhost:11434", "", "", ALLOWED)
