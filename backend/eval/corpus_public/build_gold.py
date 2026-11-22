"""Construit `gold_public.json` : questions annotées à la main sur des documents publics réservés à l'évaluation.

Chaque question de fait porte un `marker` : extrait **exact** du document (après nettoyage) qui contient la réponse ;
le script refuse de produire le fichier si un marqueur est introuvable ou si un document n'est pas dans la partie
« gold » du découpage (aucun de ces documents ne sert à l'entraînement). Les questions « sans preuve » portent des
termes `absent_terms` qui ne doivent figurer nulle part dans le document : la réponse attendue est un refus.

Usage (racine du dépôt, venv du backend) : python backend/eval/corpus_public/build_gold.py
Prérequis : `python -m training.dataset.real` (découpage training/data/real/groups.json).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from training.dataset import real
from training.dataset.extract import load_manifest, read_document

OUT = Path(__file__).with_name("gold_public.json")

# (document, question, réponse attendue, marqueur exact)
FACTS = [
    ("wb-27148", "De combien le coût de construction en Ukraine dépasse-t-il celui de l'UE ?", "22 %",
     "the cost of construction in Ukraine is 22 percent higher than in the EU"),
    ("wb-27148", "By how much did the Ukrainian economy contract per year in 2014-2015?", "8.7 percent per year",
     "contracted sharply by 8.7 percent per year during 2014"),
    ("wb-27148", "What was Ukraine's unemployment rate in the second half of 2015?", "9.5 percent",
     "from 8 percent in 2013 to 9.5 percent in the second half of 2015"),
    ("wb-27559", "How large is the exclusive economic zone of Seychelles?", "about 1.4 million km2",
     "exclusive economic zone (EEZ) of approximately 1.4 million km2"),
    ("wb-27559", "What is the overall unemployment level in Seychelles?", "approximately 4 percent",
     "overall unemployment level of approximately 4 percent"),
    ("wb-27559", "What share of workers in Seychelles belongs to a trade union?", "2 percent",
     "only 2 percent of workers indicating that they belong to a trade union"),
    ("wb-30225", "By how much is GDP estimated to have increased in Seychelles in 2017?", "5.3 percent",
     "GDP in 2017 is estimated to have increased by 5.3 percent"),
    ("wb-30225", "Which national plan for 2018-2022 does the framework mention for Seychelles?",
     "the National Development Plan for 2018-2022", "National Development Plan for 2018-2022"),
    ("wb-27563", "What level of annual investment lending did the Ukraine CPS foresee for its first two years?",
     "about US$500 million per year", "base-level support in the range of US$500 million per year"),
    ("wb-27563", "Until when was the moratorium on private agricultural land sales extended in Ukraine?",
     "end-2017", "moratorium on land sales extended until end-2017"),
    ("wb-29702", "How many smallholder households in Zambia are linked to the private sector through outgrower schemes?",
     "400,000", "400,000 smallholder households are linked to the private sector"),
    ("wb-29702", "By how many points did the share of adults with a formal account rise in Zambia between 2011 and 2014?",
     "15 percentage points", "increased by 15 percentage points"),
    ("wb-29702", "What share of the two poorest quintiles in Zambia can enter grade 8?", "18 percent",
     "Only 18 percent from the bottom (poorest) two quintiles can enter grade 8"),
    ("wb-29702", "What share of the rural population of Zambia has access to electricity?", "4 percent",
     "only 4 percent of the rural population has access to electricity"),
    ("eu-52020SC0120-en", "What de minimis position limit was reached in early 2018 under MiFID II?", "2 500 lots",
     "de minimis position limit of 2 500 lots"),
    ("eu-52020SC0120-en", "What amount do stakeholders mention firms spent to implement the research requirements?",
     "around EUR 1 million", "numbers around EUR 1 million"),
    ("eu-52020SC0120-en", "When did the public consultation on MiFID II/MiFIR end?", "18 May 2020",
     "public consultation on MiFID II/MiFIR which ended on 18 May 2020"),
    ("eu-52020SC0142-en", "By how much did turnover of emerging market currencies rise in the three years to 2019?",
     "almost 60%", "the turnover of emerging market currencies rose by almost 60%"),
    ("eu-52020PC0337-en", "How many respondents answered the Commission's consultation on the Benchmark Regulation?",
     "22", "responses from 22 respondents"),
    ("eu-52020PC0337-en", "What is the legal basis of the proposal amending the Benchmark Regulation?",
     "Article 114 TFEU", "Article 114 of the Treaty on the Functioning of the European Union"),
    ("eu-52020PC0280-en", "Within what time must Member States adopt the transposition measures of the MiFID proposal?",
     "9 months from the entry into force", "9 months from the entry into force of this Directive"),
    ("wbfr-28327159", "Quelle part de l'économie mauritanienne ce secteur représentait-il en moyenne entre 2005 et 2015 ?",
     "16 pour cent", "16 pour cent entre 2005 et 2015"),
    ("wbfr-28327159", "Quel rang la Mauritanie occupait-elle à l'indice de développement humain en 2014 ?",
     "153e sur 186", "153e place parmi 186 pays"),
    ("wbfr-28327159", "À combien se sont élevées les recettes fiscales en Mauritanie entre 2012 et 2014 ?",
     "17,4 pour cent du PIB", "17,4 pour cent du PIB entre 2012 et 2014"),
    ("wbfr-28327159", "En quelle année la loi foncière mauritanienne a-t-elle créé un cadre pour les droits fonciers ?",
     "1983", "La loi foncière de 1983"),
    ("wbfr-31149680", "De combien le taux de pauvreté a-t-il été ramené en Mauritanie entre 2008 et 2014 ?",
     "de 44,5 à 33 pour cent", "de 44,5 à 33 pour cent"),
    ("wbfr-31149680", "Combien d'abonnés pour 100 personnes le projet WARCIP a-t-il permis de desservir ?",
     "25,9 pour un objectif de 10", "25,9 abonnés pour 100 personnes contre un objectif de 10 pour 100"),
    ("wbfr-33920584", "Quelle catastrophe a illustré la capacité de coordination de la DGPC et du SNGRD en Haïti ?",
     "le tremblement de terre de 2021", "réponse au tremblement de terre de 2021"),
    ("wbfr-33920584", "Jusqu'à quand les restrictions de voyage et de confinement sont-elles restées en vigueur en Haïti ?",
     "août 2020", "jusqu’en août 2020"),
]
NO_EVIDENCE = [
    ("wb-27148", "What national budget is allocated to space exploration in Ukraine?", ["space exploration"]),
    ("wb-29702", "How many nuclear reactors are operating in Zambia?", ["nuclear reactor"]),
    ("wbfr-28327159", "Quel budget est alloué au programme spatial de la Mauritanie ?", ["programme spatial"]),
    ("eu-52020SC0120-en", "How many Olympic medals did the EU win in 2020?", ["olympic"]),
    ("wbfr-31149680", "Combien de brevets ont été déposés par des entreprises mauritaniennes en 2018 ?", ["brevets"]),
]


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def build() -> dict:
    entries = {e["id"]: e for e in load_manifest()}
    by_pair: dict[str, list[dict]] = {}
    for e in entries.values():
        by_pair.setdefault(e["pair"], []).append(e)
    assign = json.loads((ROOT / "training" / "data" / "real" / "groups.json").read_text("utf-8"))
    texts: dict[str, str] = {}

    def doc(doc_id: str) -> tuple[dict, str, str]:
        e = entries[doc_id]
        group = real.group_of(e, by_pair)
        if assign[group] != "gold":
            raise SystemExit(f"{doc_id} (groupe {group}) n'est pas réservé au jeu or : {assign[group]}")
        if doc_id not in texts:
            texts[doc_id] = _norm(" ".join(read_document(e) or []))
        return e, group, texts[doc_id]

    questions = []
    for n, (doc_id, q, answer, marker) in enumerate(FACTS, start=1):
        e, group, text = doc(doc_id)
        if _norm(marker) not in text:
            raise SystemExit(f"marqueur introuvable dans {doc_id} : {marker!r}")
        questions.append({"id": f"RG{n:02d}", "type": "fact", "document": doc_id, "group": group,
                          "lang": real.detect_lang([q]), "doc_lang": real.detect_lang([text]), "question": q,
                          "expected_answer": answer, "marker": marker, "expected_refusal": False})
    for k, (doc_id, q, absent) in enumerate(NO_EVIDENCE, start=len(FACTS) + 1):
        e, group, text = doc(doc_id)
        if any(t.lower() in text.lower() for t in absent):
            raise SystemExit(f"terme censé être absent trouvé dans {doc_id} : {absent}")
        questions.append({"id": f"RG{k:02d}", "type": "no_evidence", "document": doc_id, "group": group,
                          "lang": real.detect_lang([q]), "doc_lang": real.detect_lang([text]), "question": q,
                          "expected_answer": None, "marker": None, "absent_terms": absent, "expected_refusal": True})
    return {
        "description": "Jeu or réel : questions annotées sur des documents publics (CC BY) exclus de l'entraînement.",
        "licences": "voir data/LICENCES.md ; documents : data/public/manifest.json",
        "annotation": "questions écrites à la main d'après le texte ; marqueur exact vérifié par script",
        "questions": questions,
    }


def main() -> None:
    gold = build()
    OUT.write_text(json.dumps(gold, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(gold['questions'])} questions écrites dans {OUT}")


if __name__ == "__main__":
    main()
