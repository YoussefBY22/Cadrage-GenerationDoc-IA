"""Re-rendu des exemples du pilote v2 avec les fonctions ACTUELLES de l'application.

Les invites v2 datent d'avant plusieurs changements de gabarits et de prompts. On en reprend seulement les
DONNÉES (passages, titre de section, réponse relue) et on refait l'invite avec `app.generation.prompting` et
les gabarits d'aujourd'hui : un titre qui correspond à une section d'un gabarit (tor, cdc, roadmap, findings)
reprend la consigne, les références et les limites du gabarit ; sinon la consigne et les limites lues dans
l'ancienne invite sont conservées (questions libres).

Aucun chemin en dur : le fichier v2 est donné en argument.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.domain.retrieval import Passage
from app.generation import prompting
from app.generation.llm_schemas import LLMSection
from app.generation.template_loader import SectionSpec, load_template
from app.verification import resolve_labels, verify_section

from training.dataset.v3_build import LANG, _chunk

_PASSAGE = re.compile(r"<<PASSAGE id=(P\d+) nonce=(\w+)>>\n(.*?)\n<<FIN nonce=\2>>", re.DOTALL)
_SECTION = re.compile(r"^SECTION : (.*)$", re.MULTILINE)
_INSTR = re.compile(r"^CONSIGNE : (.*)$", re.MULTILINE)
_LIMITS = re.compile(r"^Au plus (\d+) phrases ; au moins (\d+) passage", re.MULTILINE)
TEMPLATE_TYPES = ("roadmap", "tor", "cdc")
LICENCE_V2 = "Décision 2011/833/UE (réutilisation, CC BY 4.0)"


class Skipped(ValueError):
    """Exemple qui ne correspond plus à ce que l'application envoie (section rendue sans modèle)."""


def template_section_by_title(title: str) -> tuple[str, SectionSpec] | None:
    for t in TEMPLATE_TYPES:
        for s in load_template(t, LANG).sections:
            if s.title == title:
                if s.requires_decisions:
                    raise Skipped(f"« {title} » exige des décisions humaines : l'application ne l'envoie pas au modèle")
                return f"gabarit:{t}/{s.key}", s
    return None


def parse_user(user: str) -> dict:
    """Passages, titre, consigne et limites de l'ancienne invite utilisateur."""
    passages = [(m.group(1), m.group(3)) for m in _PASSAGE.finditer(user)]
    title, instr, lim = _SECTION.search(user), _INSTR.search(user), _LIMITS.search(user)
    if not (passages and title and instr and lim):
        raise ValueError("invite v2 illisible : passages, section, consigne ou limites manquants")
    return {"passages": passages, "title": title.group(1), "instructions": instr.group(1),
            "max_sentences": int(lim.group(1)), "min_sources": int(lim.group(2))}


def spec_for(parsed: dict) -> tuple[str, SectionSpec]:
    found = template_section_by_title(parsed["title"])
    if found:
        return found
    q = parsed["title"]
    return "libre", SectionSpec(key="question", title=q, instructions=parsed["instructions"],
                                queries=[q, f"{q} preuves"], max_sentences=parsed["max_sentences"],
                                min_sources=parsed["min_sources"])


def rerender(example: dict) -> dict:
    """Exemple v2 -> exemple au format du pilote v3 (messages + meta.rendu), invite refaite."""
    old, meta = example["messages"], example["meta"]
    parsed = parse_user(old[1]["content"])
    origin, spec = spec_for(parsed)
    source = f"ue-{meta['diagnostic']}"
    nonce = hashlib.sha256(meta["id"].encode()).hexdigest()[:12]
    chunks = [_chunk(source, meta["id"], i, text, spec.title) for i, (_, text) in enumerate(parsed["passages"])]
    passages = [Passage(label=lab, chunk=c, score=1.0 / (i + 1), ranks={"bm25": i + 1})
                for i, ((lab, _), c) in enumerate(zip(parsed["passages"], chunks, strict=True))]
    user = prompting.build_section_prompt(spec, passages, nonce=nonce, lang=LANG)
    llm = LLMSection.model_validate(json.loads(old[2]["content"]))
    rep = verify_section(resolve_labels(llm, passages, section_key=spec.key),
                         {p.chunk.id: p.chunk for p in passages}, dossier_id=meta["id"])
    new_meta = {
        "id": meta["id"], "kind": meta["kind"], "lang": "fr", "real": True, "source": source,
        "source_titre": f"Analyse d'impact de la Commission européenne, CELEX {meta['diagnostic']}",
        "licence": LICENCE_V2, "licence_preuve": "https://eur-lex.europa.eu/eli/dec/2011/833/oj",
        "split": None, "lot": "pilote-v2",
        "consigne_ecrite_par": "gabarit de l'application" if origin != "libre" else "assistant",
        "sortie_ecrite_par": meta.get("sortie_ecrite_par", ""),
        "valide_par_humain": False, "relu_par": meta.get("relu_par"), "statut_relecture": meta.get("statut_relecture"),
        "tpv": rep.tpv, "bloquants": [i.code for i in rep.issues if i.severity == "blocking"],
        "rendu": {"nonce": nonce, "tache": "section", "spec": spec.model_dump(), "spec_origine": origin,
                  "passages": [{"label": p.label, "texte": p.chunk.text, "titre": spec.title} for p in passages]},
    }
    messages = [{"role": "system", "content": prompting.system_prompt(LANG)},
                {"role": "user", "content": user}, old[2]]
    return {"messages": messages, "meta": new_meta}


def load_v2(path: Path, skipped: list[str] | None = None) -> list[dict]:
    """Exemples v2 re-rendus ; ceux d'une section rendue sans modèle sont écartés (leur id va dans ``skipped``)."""
    out = []
    for line in Path(path).read_text("utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        try:
            out.append(rerender(raw))
        except Skipped as e:
            if skipped is not None:
                skipped.append(f"{raw['meta']['id']} : {e}")
    return out
