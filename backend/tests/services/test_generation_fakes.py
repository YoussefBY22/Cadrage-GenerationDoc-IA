"""Faux modèles pour les tests de génération : un « honnête » (recopie et cite) et un « tricheur »."""

import re

from app.llm.base import LLMError
from app.roadmap.scoring import DEFAULT_CRITERIA

_PASSAGE = re.compile(r"<<PASSAGE id=(P\d+) nonce=\w+>>\n(.*?)\n<<FIN nonce=\w+>>", re.DOTALL)


def passages_of(prompt: str) -> list[tuple[str, str]]:
    return _PASSAGE.findall(prompt)


def best_sentence(text: str) -> str:
    """La plus longue phrase (<= 300 car.) du passage : recopiée mot pour mot."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
    ok = [p for p in parts if len(p) <= 300 and len(p.split()) >= 5]
    return max(ok or parts, key=len)


def _scores(v: int) -> list[dict]:
    return [{"key": c.key, "value": v, "sources": ["P1"], "rationale": "Selon le passage."}
            for c in DEFAULT_CRITERIA]


def honest(prompt: str, schema) -> dict:
    ps = passages_of(prompt)
    name = schema.__name__
    if name == "LLMFindings":
        return {"status": "ok", "findings": [
            {"text": best_sentence(t), "theme": "gouvernance", "severity": "medium", "sources": [p]}
            for p, t in ps[:2]]}
    if name == "LLMSection":
        sent = [{"text": best_sentence(t), "kind": "fact", "sources": [p],
                 "findings": ["F1"] if "F1:" in prompt else []} for p, t in ps[:2]]
        return {"status": "ok", "sentences": sent}
    if name == "LLMInitiatives":
        nf = len(re.findall(r"^F\d+:", prompt, re.MULTILINE))
        return {"initiatives": [
            {"title": "Initiative A", "description": "Première initiative.", "findings": ["F1"],
             "scores": _scores(5)},
            {"title": "Initiative B", "description": "Seconde initiative.",
             "findings": ["F2" if nf > 1 else "F1"], "scores": _scores(2),
             "depends_on_titles": ["Initiative A"]}]}
    raise AssertionError(name)


def cheater(prompt: str, schema) -> dict:
    """Fausse étiquette (P99) et chiffre inventé, présentés comme des faits."""
    if schema.__name__ == "LLMSection":
        return {"status": "ok", "sentences": [
            {"text": "Le budget atteint 98765 euros selon le rapport.", "kind": "fact",
             "sources": ["P99"]},
            {"text": "Le comité se réunit chaque semaine sans aucune source.", "kind": "fact",
             "sources": []}]}
    return honest(prompt, schema)


class FlakyOnce:
    """Première réponse invalide (LLMError), les suivantes honnêtes."""

    def __init__(self):
        self.n = 0

    def __call__(self, prompt, schema):
        self.n += 1
        if self.n == 1:
            raise LLMError("JSON invalide")
        return honest(prompt, schema)
