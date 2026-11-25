"""Position d'une institution sur une recommandation, et conflit d'une recommandation avec la stratégie.

Appel minimal et sans effet de bord : il lit des passages, demande un JSON ``LLMStance`` et fait vérifier chaque
phrase de justification. Il ne crée ni ne valide aucune décision (le verrou d'approbation n'est pas touché).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.config import Settings, get_settings
from app.domain.generation import SectionDraft, Sentence
from app.domain.retrieval import Passage
from app.generation.llm_schemas import LLMStance
from app.generation.prompting import build_stance_prompt, passage_budget, system_prompt
from app.llm.base import LLMProvider
from app.verification import verify_section

from .generation import call_model, new_nonce

STANCE_REPLY_TOKENS = 500


def assess(provider: LLMProvider, mode: str, passages: Sequence[Passage], *, dossier_id: str,
           lang: str = "fr", settings: Settings | None = None) -> dict:
    """{stance, sentences, report} ; ``stance`` est ``None`` si le modèle refuse ou répond mal."""
    settings = settings or get_settings()
    nonce = new_nonce()
    fixed = system_prompt(lang) + build_stance_prompt(mode, [], nonce=nonce, lang=lang)
    budget = passage_budget(getattr(provider, "context_tokens", None), fixed, STANCE_REPLY_TOKENS)
    prompt = build_stance_prompt(mode, passages, nonce=nonce, budget=budget, lang=lang)
    llm, attempts, latency, error = call_model(provider, prompt, LLMStance, lang=lang)
    if llm is None:
        return {"stance": None, "sentences": [], "report": None, "attempts": attempts, "error": error}
    by_label = {p.label: p.chunk for p in passages}
    sentences = [Sentence(text=s.text, kind=s.kind, source_labels=list(s.sources),
                          source_ids=[by_label[x].id for x in s.sources if x in by_label] or list(s.sources))
                 for s in llm.sentences]
    report = verify_section(SectionDraft(section_key="stance", status=llm.status, sentences=sentences),
                            {c.id: c for c in by_label.values()}, dossier_id=dossier_id,
                            support_threshold=settings.support_threshold, lang=lang)
    return {"stance": llm.stance if llm.status == "ok" else None, "status": llm.status,
            "sentences": [s.text for s in sentences], "report": report.model_dump(mode="json"),
            "attempts": attempts, "latency_ms": latency}
