"""Limites en vigueur, rangées selon ce dont elles dépendent (15 §7), et budget de la fenêtre de contexte.

Trois familles, jamais mélangées : limite du MODÈLE, du MOTEUR et du matériel, de l'APPLICATION.
"""

from __future__ import annotations

from app.generation.prompting import SYSTEM_PROMPT_FR, passage_budget, safe_tokens
from app.llm.ollama import DEFAULT_NUM_CTX
from app.services.generation import SECTION_REPLY_TOKENS

FORMATS = ["PDF", "DOCX", "PPTX", "TXT", "MD"]
CONTEXT_OVERHEAD_TOKENS = 200   # consigne de section et fiche de contexte (estimation)
AVG_PASSAGE_TOKENS = 350        # taille moyenne d'un passage, pour estimer un nombre de passages
SATURATION = [
    "Le moteur refuse tout dépassement : aucune coupe silencieuse du début de la requête.",
    "Constats : les passages sont répartis en lots, aucun n'est abandonné.",
    "Sections : les passages qui ne tiennent pas ne sont pas envoyés ; le modèle ne cite que ceux envoyés.",
]


def allocated_context(settings) -> int:
    return int(settings.ollama_num_ctx or DEFAULT_NUM_CTX)


def build_limits(settings, card: dict | None, loaded: dict | None = None) -> dict:
    """Limites pour le modèle `card` (fiche de `engine.describe`) ; `loaded` : entrée de `/api/ps` si chargé."""
    card = card or {}
    caps = card.get("capabilities")
    return {
        "model": {
            "max_context": card.get("max_context"),
            "vision": None if caps is None else "vision" in caps,
            "capabilities": caps,
        },
        "engine": {
            "allocated_context": allocated_context(settings),
            "allocated_source": "config" if settings.ollama_num_ctx else "default",
            "loaded_context": (loaded or {}).get("context_length"),
            "vram_bytes": (loaded or {}).get("size_vram"),
            "gpu_layers": settings.ollama_num_gpu,
            "keep_alive": settings.ollama_keep_alive,
        },
        "app": {
            "response_reserved": SECTION_REPLY_TOKENS,
            "max_upload_mb": settings.max_upload_mb,
            "formats": FORMATS,
            "images_used": False,
            "saturation": SATURATION,
        },
    }


def context_budget(settings, max_context: int | None, candidate_tokens: int | None = None) -> dict:
    """Répartition de la fenêtre pour une section : valeurs du type `ContextBudget` (docs/15, API Modèles).

    `candidate_tokens` : taille des passages retrouvés ; ce qui ne tient pas est « non envoyé ».
    """
    window = allocated_context(settings)
    candidates = (settings.retrieval_k * AVG_PASSAGE_TOKENS if candidate_tokens is None
                  else max(0, candidate_tokens))
    system = safe_tokens(SYSTEM_PROMPT_FR)
    context = CONTEXT_OVERHEAD_TOKENS
    capacity = passage_budget(window, "", SECTION_REPLY_TOKENS) - system - context
    capacity = max(0, capacity)
    passages = min(candidates, capacity)
    unsent = candidates - passages
    return {
        "unit": "tokens", "estimated": True,
        "window_allocated": window, "window_max": max_context,
        "system": system, "context": context, "passages": passages,
        "response_reserved": SECTION_REPLY_TOKENS,
        "free": max(0, window - system - context - passages - SECTION_REPLY_TOKENS),
        "passages_unsent": unsent,
        "passages_unsent_count": -(-unsent // AVG_PASSAGE_TOKENS) if unsent else 0,
    }
