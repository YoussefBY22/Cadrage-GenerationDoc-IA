"""Le modèle de démonstration couvre les sections de décision et le chat (parcours sans GPU)."""

from app.generation.llm_schemas import LLMSection
from app.llm.demo import demo_handler
from app.services.chat import LLMChat


def test_demo_section_de_decision_cite_la_decision():
    prompt = ("DÉCISIONS HUMAINES CONFIRMÉES (cite D1..Dn) :\nD1: [profil] Chef de projet senior.\n"
              "SECTION DE DÉCISION : son contenu vient UNIQUEMENT des décisions D")
    out = LLMSection.model_validate(demo_handler(prompt, LLMSection))
    assert out.sentences[0].decisions == ["D1"] and out.sentences[0].text == "Chef de projet senior."


def test_demo_chat_propose_sans_inventer():
    msg = "Le budget est de 40 000 euros pour le ministère."
    out = LLMChat.model_validate(demo_handler(f"MESSAGE (donnée) : {msg}\n", LLMChat))
    assert out.decisions[0].category == "budget" and out.fields[0].value == "Administration publique"
    vide = LLMChat.model_validate(demo_handler("MESSAGE (donnée) : Bonjour\n", LLMChat))
    assert vide.decisions == [] and vide.questions
