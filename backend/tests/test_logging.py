import io
import json
import logging

from app.logging_setup import JsonFormatter, fingerprint


def test_sensitive_fields_never_logged_in_clear():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    lg = logging.getLogger("t")
    lg.handlers = [handler]
    lg.setLevel("INFO")
    lg.info("génération", extra={"prompt": "Le budget du client ACME est de 1 200 000 MAD",
                                 "duration_ms": 12})
    line = buf.getvalue()
    assert "ACME" not in line and "1 200 000" not in line
    rec = json.loads(line)
    assert rec["prompt"] == fingerprint("Le budget du client ACME est de 1 200 000 MAD")
    assert rec["duration_ms"] == 12
