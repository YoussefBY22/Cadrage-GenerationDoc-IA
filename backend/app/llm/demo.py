"""Modèle de démonstration « honnête » : recopie la meilleure phrase des passages et la cite.

Sert à dérouler le produit de bout en bout sans GPU (`LLM_PROVIDER=demo`). Il ne comprend rien :
chaque phrase produite est une phrase existante d'un passage fourni, donc vérifiable.
"""

import re

_PASSAGE = re.compile(r"<<PASSAGE id=(P\d+) nonce=\w+>>\n(.*?)\n<<FIN nonce=\w+>>", re.DOTALL)


def _best_sentence(text: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
    ok = [p for p in parts if len(p) <= 300 and len(p.split()) >= 5 and "|" not in p]
    return max(ok or parts, key=len)


_MESSAGE = re.compile(r"^MESSAGE \(donnée\) : (.*)$", re.MULTILINE)


def _chat(prompt: str) -> dict:
    """Chat de démonstration : relève budget, durée et profil dans le message, rien d'autre."""
    found = _MESSAGE.search(prompt)
    msg = found.group(1) if found else ""
    low = msg.lower()
    decisions, fields = [], []
    for word, cat in (("budget", "budget"), ("profil", "profile"), ("délai", "schedule"),
                      ("durée", "duration"), ("critère", "criterion")):
        if word in low:
            decisions.append({"category": cat, "text": msg.strip().rstrip(".") + "."})
            break
    if "ministère" in low or "administration" in low:
        fields.append({"field": "sector", "value": "Administration publique"})
    asked = [] if decisions else ["Quel budget, quel profil et quel calendrier envisagez-vous ?"]
    return {"reply": "Je note cela. Confirmez ce qui est juste." if decisions or fields
            else "Pouvez-vous préciser le contexte du projet ?",
            "questions": asked, "fields": fields, "decisions": decisions}


def demo_handler(prompt: str, schema) -> dict:
    """Réponse structurée déterministe pour chaque schéma de génération."""
    from app.roadmap.scoring import DEFAULT_CRITERIA

    ps = _PASSAGE.findall(prompt)
    name = schema.__name__
    if name == "LLMFindings":
        return {"status": "ok", "findings": [
            {"text": _best_sentence(t), "theme": "gouvernance", "severity": "medium", "sources": [p]}
            for p, t in ps[:2]]}
    if name == "LLMChat":
        return _chat(prompt)
    if name == "LLMSection" and "SECTION DE DÉCISION" in prompt:
        # section de décision : on reformule la décision D1, jamais un constat du diagnostic
        found = re.search(r"^D1: \[[^\]]*\] (.*)$", prompt, re.MULTILINE)
        text = found.group(1) if found else "Décision à préciser."
        return {"status": "ok", "sentences": [
            {"text": text, "kind": "fact", "sources": [], "decisions": ["D1"]}]}
    if name == "LLMSection":
        if not ps:
            return {"status": "insufficient_evidence", "sentences": [],
                    "missing_evidence": "Aucun passage pertinent."}
        return {"status": "ok", "sentences": [
            {"text": _best_sentence(t), "kind": "fact", "sources": [p],
             "findings": ["F1"] if "F1:" in prompt else []} for p, t in ps[:2]]}
    if name == "LLMInitiatives":
        def scores(v):
            return [{"key": c.key, "value": v, "sources": ["P1"], "rationale": "Selon le passage."}
                    for c in DEFAULT_CRITERIA]
        nf = len(re.findall(r"^F\d+:", prompt, re.MULTILINE))
        return {"initiatives": [
            {"title": "Initiative A", "description": "Première initiative.", "findings": ["F1"],
             "scores": scores(5)},
            {"title": "Initiative B", "description": "Seconde initiative.",
             "findings": ["F2" if nf > 1 else "F1"], "scores": scores(2),
             "depends_on_titles": ["Initiative A"]}]}
    raise ValueError(f"schéma non géré par le modèle de démonstration : {name}")
