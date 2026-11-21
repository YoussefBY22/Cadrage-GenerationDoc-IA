"""Modèle simulé : cite correctement ou triche selon des taux fixés. SIMULATION : sans valeur scientifique."""

import hashlib
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.llm.base import LLMError

CANARY = "ZX-CANARI-7"
NOTICE = "simulation : sans valeur scientifique"
_PASSAGE = re.compile(r"<<PASSAGE id=(P\d+) nonce=\w+>>\n(.*?)\n<<FIN nonce=\w+>>", re.DOTALL)
_TITLE = re.compile(r"^SECTION : (.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Rates:
    false_citation: float = 0.0       # phrase citant une étiquette inexistante
    invented_number: float = 0.0      # phrase avec un chiffre absent des sources
    trap_obedience: float = 0.0       # reprise du canari d'un passage piégé
    invalid_json: float = 0.0         # 1er essai invalide (LLMError)
    missed_refusal: float = 0.0       # ne refuse pas une section sans preuve
    no_evidence_titles: frozenset[str] = field(default_factory=frozenset)


def _best(text: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
    ok = [p for p in parts if len(p) <= 300 and len(p.split()) >= 5]
    return max(ok or parts or [text], key=len)


def make_handler(rates: Rates, seed: int = 0) -> Callable:
    """Handler FakeProvider déterministe : même (graine, prompt, rang de l'appel) -> même sortie."""
    seen: dict[str, int] = {}

    def handler(prompt: str, schema) -> dict:
        ps = _PASSAGE.findall(prompt)
        found = _TITLE.search(prompt)
        title = found.group(1) if found else ""
        # clé indépendante du nonce (aléatoire) et de l'ordre des passages (égalités de score)
        key = f"{schema.__name__}|{title}|" + "|".join(sorted(t for _, t in ps))
        n = seen[key] = seen.get(key, 0) + 1
        h = hashlib.sha256(f"{seed}|{key}".encode()).digest()
        rng = random.Random(int.from_bytes(h[:8], "big"))
        if n == 1 and rng.random() < rates.invalid_json:
            raise LLMError("JSON invalide (simulé)")
        name = schema.__name__
        if name == "LLMFindings":
            return {"status": "ok", "findings": [_sentence(rng, rates, p, t, extra=True)
                                                 for p, t in sorted(ps, key=lambda x: x[1])[:2]]}
        if name == "LLMInitiatives":
            return _initiatives(prompt)
        if title in rates.no_evidence_titles and rng.random() >= rates.missed_refusal:
            return {"status": "insufficient_evidence", "sentences": [],
                    "missing_evidence": "Aucun passage ne traite ce sujet."}
        if not ps:  # config A : aucune pièce, le modèle « invente »
            return {"status": "ok", "sentences": [
                {"text": "La situation est globalement satisfaisante.", "kind": "fact",
                 "sources": []}]}
        sentences = []
        for p, t in sorted(ps, key=lambda x: x[1])[:3]:
            s = _sentence(rng, rates, p, t)
            sentences.append({"text": s["text"], "kind": "fact", "sources": s["sources"],
                              "findings": []})
        return {"status": "ok", "sentences": sentences}

    return handler


def _sentence(rng: random.Random, rates: Rates, label: str, text: str, extra: bool = False) -> dict:
    body = _best(text).replace(CANARY, "").strip()  # un modèle sain ne recopie pas le canari
    if CANARY in text and rng.random() < rates.trap_obedience:
        body = f"{CANARY} {body}"
    if rng.random() < rates.invented_number:
        body += " soit 98765 unités"
    sources = ["P99"] if rng.random() < rates.false_citation else [label]
    out = {"text": body, "sources": sources}
    if extra:
        out |= {"theme": "diagnostic", "severity": "medium"}
    return out


def _initiatives(prompt: str) -> dict:
    from app.roadmap.scoring import DEFAULT_CRITERIA

    nf = len(re.findall(r"^F\d+:", prompt, re.MULTILINE))
    sc = [{"key": c.key, "value": 3, "sources": ["P1"], "rationale": "Simulé."}
          for c in DEFAULT_CRITERIA]
    return {"initiatives": [
        {"title": "I1 Socle", "description": "Simulée.", "findings": ["F1"], "scores": sc},
        {"title": "I2 Suite", "description": "Simulée.", "findings": ["F2" if nf > 1 else "F1"],
         "scores": sc, "depends_on_titles": ["I1 Socle"]}]}
