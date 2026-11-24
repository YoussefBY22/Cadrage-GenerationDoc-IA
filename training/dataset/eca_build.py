"""Exemples d'entraînement tirés des rapports spéciaux de la Cour des comptes européenne et des réponses de la Commission.

Cinq tâches (champ ``meta.task_type``), toutes avec les invites que l'application envoie vraiment :
- ``extraction`` : paragraphes du rapport (et recommandation + échéance) -> ``LLMFindings`` ;
- ``position`` : recommandation + réponse de la Commission -> accept / partial / reject + justification citée ;
- ``conflit`` : recommandation + justification d'une réponse partielle ou d'un rejet (aligned si acceptée) ;
- ``feuille_de_route`` : recommandations et leurs échéances réelles -> initiatives ordonnées, aucune date inventée ;
- ``refus`` : la preuve est retirée -> ``insufficient_evidence``.

Toutes les phrases de sortie sont recopiées des documents (assemblage mécanique « amorce + alinéa » pour les
recommandations). Seuls sont écrits ici : le thème et la gravité des constats (règles, ci-dessous) et le texte
de ``missing_evidence`` des refus. Les deux sont marqués dans ``meta``.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

from app.domain.retrieval import Passage
from app.generation import prompting
from app.generation.llm_schemas import LLMFindings, LLMSection, LLMStance
from app.generation.template_loader import load_template
from app.verification import resolve_labels, verify_section

from training.dataset import eca_parse as P
from training.dataset import schema_order
from training.dataset.v3_build import LANG, _chunk, assemble, contains

MAX_PASSAGE_WORDS = 480  # l'entraînement coupe à 2048 jetons : invite (~400) + passages (~480 mots = ~900 jetons)
TASKS = ("extraction", "position", "conflit", "feuille_de_route", "refus", "axes")
KIND = {"extraction": "extraction de constats", "position": "position sur une recommandation",
        "conflit": "conflit avec une contrainte", "feuille_de_route": "feuille de route", "refus": "refus",
        "axes": "axes de la feuille de route"}
LICENCE_REP = "CC BY 4.0 (Cour des comptes européenne, décision n° 6-2019) ; réponses : décision 2011/833/UE, CC BY 4.0"
LICENCE = "CC BY 4.0 (Cour des comptes européenne, décision n° 6-2019)"
PREUVE = "https://www.eca.europa.eu/fr/legal-notice"

_CUES = re.compile(r"\b(nous avons (?:constaté|relevé|observé|noté|conclu|estimé)|n[’']a pas|n[’']ont pas|ne sont pas|"
                   r"n[’']est pas|insuffisan|lacune|retard|manque|absence|limité|faible|risque|trop tard|"
                   r"ne dispos|sans |peu de)", re.IGNORECASE)
_FIND = re.compile(r"nous avons (?:constaté|relevé|observé|conclu)|n[’']a pas|n[’']ont pas|insuffisan|lacune|"
                   r"absence|ne dispos|n[’']est pas|ne sont pas|trop tard|ne permet", re.IGNORECASE)
_YEAR = re.compile(r"\b20\d\d\b")
_THEMES = [(r"suivi|évalu|indicateur|mesure[rs]? d", "suivi et évaluation"), (r"financ|budget|fonds|coût|dépense", "financement"),
           (r"délai|retard|calendrier|tard", "délais"), (r"données|information|statistique", "données"),
           (r"conform|règle|législ|droit|directive|règlement", "conformité"),
           (r"contrôle|audit|vérif|supervis", "contrôle"), (r"coordination|gouvernance|responsab|rôle", "gouvernance"),
           (r"risque|fraude|irrégularit", "risques")]
_HIGH = re.compile(r"n[’']a pas|n[’']ont pas|insuffisan|lacune|absence|ne dispos|aucun|n[’']est pas", re.IGNORECASE)
_MED = re.compile(r"parfois|partiel|limité|faible|retard|toutefois|cependant|peu de", re.IGNORECASE)
MISSING = {
    "echeance": "Les passages décrivent des constats mais ne donnent aucune échéance.",
    "position": "Aucun passage ne donne la position de l'institution sur la recommandation.",
    "contrainte": "Aucun passage ne contient de stratégie, de priorité ou de contrainte à comparer à la recommandation.",
}


def _findings_in(paragraph: str) -> list[str]:
    """Phrases du paragraphe qui énoncent un constat (8 à 55 mots, sans citation)."""
    body = P._PARA.sub("", paragraph)
    return [x for x in P.sentences(body) if 8 <= P.words(x) <= 55 and _FIND.search(x) and "«" not in x]


def theme_of(text: str) -> str:
    low = text.lower()
    for pat, theme in _THEMES:
        if re.search(pat, low):
            return theme
    return "constat d'audit"


def severity_of(text: str) -> str:
    return "high" if _HIGH.search(text) else "medium" if _MED.search(text) else "low"


def _section(kind: str, key: str):
    return next(s for s in load_template(kind, LANG).sections if s.key == key)


def rec_sentence(rec: P.Rec, letter: str | None = None) -> tuple[str, str] | None:
    """(texte de la recommandation, passage qui la contient) ; None si elle ne se recopie pas proprement."""
    if rec.items:
        pick = [it for it in rec.items if letter is None or it[0] == letter]
        if not pick:
            return None
        if letter is None and len(pick) > 1:  # plusieurs alinéas : tels qu'ils figurent dans le passage
            text = " ".join([rec.lead] + [f"{a}) {t}" for a, t in pick])
            return (text, rec.lead) if P.words(text) <= 90 else None
        return assemble(rec.lead, pick[0][1]), rec.lead
    return rec.lead.strip(), rec.lead


def rec_passage(rec: P.Rec, letter: str | None, with_quand: bool) -> str:
    items = [it for it in rec.items if letter is None or it[0] == letter]
    parts = [rec.lead] + [f"{a}) {t}" for a, t in items]
    if with_quand:
        parts.append(f"Quand? {rec.quand}")
    return " ".join(parts)


class Builder:
    """Fabrique un exemple : mélange des étiquettes, invite de l'application, vérificateur, méta."""

    def __init__(self, report: dict, rng: random.Random):
        self.report, self.rng = report, rng
        self.counter: Counter[str] = Counter()

    def make(self, task: str, label: str, passages: list[str], build_answer, *, spec=None, mode: str | None = None,
             origine: str, extra_meta: dict | None = None) -> dict | None:
        """``build_answer(labels)`` -> dict de réponse, ``labels[i]`` étant l'étiquette du passage ``i`` (avant mélange)."""
        if sum(P.words(p) for p in passages) > MAX_PASSAGE_WORDS or any("�" in p for p in passages):
            return None
        rid = self.report["id"]
        self.counter[task] += 1
        ex_id = f"{rid}-{label}-{self.counter[task]}"
        order = list(range(len(passages)))
        self.rng.shuffle(order)
        lab = {old: f"P{new}" for new, old in enumerate(order, 1)}
        title = spec.title if spec else {"extraction": "Constats du diagnostic", "position": "Position sur la recommandation",
                                        "conflit": "Conflit avec la contrainte", "refus": "Position"}.get(task, task)
        chunks = [_chunk(rid, ex_id, j, passages[old], title) for j, old in enumerate(order)]
        pas = [Passage(label=f"P{i}", chunk=c, score=1.0 / i, ranks={"bm25": i}) for i, c in enumerate(chunks, 1)]
        nonce = hashlib.sha256(ex_id.encode()).hexdigest()[:12]
        if spec is not None:
            user = prompting.build_section_prompt(spec, pas, nonce=nonce, lang=LANG)
        elif mode:
            user = prompting.build_stance_prompt(mode, pas, nonce=nonce, lang=LANG)
        else:
            user = prompting.build_findings_prompt(pas, nonce=nonce, lang=LANG)
        answer = build_answer(lab)
        model = LLMFindings if "findings" in answer else LLMStance if "stance" in answer or mode else LLMSection
        content = schema_order.dumps(model, answer)
        meta = {
            "id": ex_id, "kind": KIND[task], "task_type": task, "lang": "fr", "real": True, "source": rid,
            "source_titre": self.report.get("titre", rid), "source_url": self.report["url"], "licence": LICENCE_REP if
            self.report.get("reponse") else LICENCE, "licence_preuve": PREUVE, "split": None, "lot": "eca-2023-2026",
            "consigne_ecrite_par": "application", "sortie_ecrite_par": origine, "valide_par_humain": False,
            "rendu": {"nonce": nonce, "tache": "constats" if "findings" in answer else (mode or "section"),
                      "spec": spec.model_dump() if spec else None,
                      "spec_origine": f"gabarit:roadmap/{spec.key}" if spec else ("constats" if "findings" in answer else mode),
                      "passages": [{"label": p.label, "texte": p.chunk.text, "titre": title} for p in pas]},
            **(extra_meta or {}),
        }
        return {"messages": [{"role": "system", "content": prompting.system_prompt(LANG)},
                             {"role": "user", "content": user}, {"role": "assistant", "content": content}],
                "meta": meta}

    # --- tâches ------------------------------------------------------------------------------------------------
    def roadmap(self, recs: list[P.Rec], by_year: bool) -> dict | None:
        recs = [r for r in recs if rec_sentence(r)]
        if len(recs) < 2:
            return None
        chosen = sorted(self.rng.sample(recs, min(len(recs), self.rng.choice([2, 3]))), key=lambda r: r.number)
        if by_year:
            chosen.sort(key=lambda r: (int(m.group()) if (m := _YEAR.search(r.quand)) else 9999, r.number))
        texts = [rec_passage(r, None, True) for r in chosen]
        spec = _section("roadmap", "calendrier" if by_year else "initiatives")

        def answer(lab):
            sents = []
            for i, r in enumerate(chosen):
                text, _ = rec_sentence(r)
                sents.append({"text": text, "kind": "recommendation", "sources": [lab[i]], "findings": []})
                sents.append({"text": r.quand, "kind": "fact", "sources": [lab[i]], "findings": []})
            return {"status": "ok", "sentences": sents, "missing_evidence": None}

        return self._check(self.make("feuille_de_route", "fdr", texts, answer, spec=spec, origine="recommandations recopiées "
                                     "(amorce + alinéa assemblés) et échéances recopiées, ordre " +
                                     ("des échéances" if by_year else "du rapport")), texts)

    def extraction(self, paras: list[str], rec: P.Rec | None) -> dict | None:
        cands = [p for p in paras if _findings_in(p)]
        if not cands:
            return None
        k = self.rng.choice([2, 3]) if rec is None else 2
        chosen = self.rng.sample(cands, min(k, len(cands)))
        texts = list(chosen)
        if rec is not None and rec_sentence(rec):
            texts.append(rec_passage(rec, None, True))
        found: list[tuple[int, str]] = []
        for i, p in enumerate(chosen):
            found += [(i, s) for s in _findings_in(p)[:2]]
        if len(found) < 2:
            return None
        found = found[:5]

        def answer(lab):
            fs = [{"text": s, "theme": theme_of(s), "severity": severity_of(s), "sources": [lab[i]]} for i, s in found]
            if rec is not None and rec_sentence(rec):
                ri = len(chosen)
                fs.append({"text": rec_sentence(rec)[0], "theme": "recommandation", "severity": "medium",
                           "sources": [lab[ri]]})
                fs.append({"text": rec.quand, "theme": "échéance", "severity": "low", "sources": [lab[ri]]})
            return {"status": "ok", "findings": fs}

        return self._check(self.make("extraction", "ext", texts, answer, origine="phrases recopiées ; thème et gravité "
                                     "attribués par des règles de mots-clés (assistant)",
                                     extra_meta={"theme_gravite_ecrits_par": "règles automatiques de l'assistant"}), texts)

    def stance(self, rec: P.Rec, pos: P.Position, others: list[P.Position], conflict: bool) -> dict | None:
        letter = pos.letters[0] if len(pos.letters) == 1 and any(a == pos.letters[0] for a, _ in rec.items) else None
        rs = rec_sentence(rec, letter)
        if not rs:
            return None
        paragraph = " ".join([pos.paragraph] + pos.follow)
        sents = P.sentences(paragraph)
        mine = [s for s in P.sentences(pos.paragraph + " " + " ".join(pos.follow)) if P.words(s) <= 70]
        if conflict:
            if pos.stance == "accept" and len(mine) < 2:
                return None
            if pos.stance != "accept" and len(mine) < 2:
                return None
        if not mine or len(sents) < 1:
            return None
        reply_texts = [paragraph]
        if others and self.rng.random() < 0.45:  # variante difficile : toutes les réponses de la recommandation
            reply_texts = [" ".join([o.paragraph] + o.follow) for o in others]
            if paragraph not in reply_texts:
                return None
        rep = " ".join(reply_texts)
        passages = [rec_passage(rec, letter, False), rep]
        label_stance = pos.stance if not conflict else ("aligned" if pos.stance == "accept" else "conflict")
        quoted = mine[1:3] if conflict else mine[:3]
        if conflict and pos.stance == "accept":
            quoted = mine[1:3]

        def answer(lab):
            s = [{"text": t, "kind": "fact", "sources": [lab[1]], "findings": []} for t in quoted]
            r = {"text": rs[0], "kind": "recommendation", "sources": [lab[0]], "findings": []}
            return {"status": "ok", "stance": label_stance, "sentences": ([*s, r] if conflict else [r, *s]),
                    "missing_evidence": None}

        task = "conflit" if conflict else "position"
        return self._check(self.make(task, "conf" if conflict else "pos", passages, answer,
                                     mode="conflict" if conflict else "position",
                                     origine=("phrases recopiées ; étiquette = position officielle de la Commission "
                                              "(« accepte / accepte partiellement / n'accepte pas »)"),
                                     extra_meta={"etiquette": label_stance, "position_officielle": pos.stance}), passages)

    def refusal(self, kind: str, recs: list[P.Rec], paras: list[str]) -> dict | None:
        if kind == "echeance":
            cands = [p for p in paras if not _YEAR.search(p) and _CUES.search(p)]
            if len(cands) < 2:
                return None
            texts = self.rng.sample(cands, 2)
            spec = _section("roadmap", "calendrier")
            mode = None
        else:
            if not recs or not paras:
                return None
            rec = self.rng.choice(recs)
            rs = rec_sentence(rec)
            if not rs:
                return None
            neutral = [p for p in paras if not _CUES.search(p)] or paras
            texts = [rec_passage(rec, None, False), self.rng.choice(neutral)]
            spec, mode = None, "position" if kind == "position" else "conflict"

        def answer(_lab):
            return {"status": "insufficient_evidence", "sentences": [], "missing_evidence": MISSING[kind]}

        return self._check(self.make("refus", f"refus-{kind}", texts, answer, spec=spec, mode=mode,
                                     origine="refus ; texte de missing_evidence écrit par l'assistant (modèle de phrase)",
                                     extra_meta={"refus_type": kind, "preuve_retiree": kind}), texts)

    def _check(self, ex: dict | None, passages: list[str]) -> dict | None:
        """Chaque phrase doit être recopiée d'un passage ; le vérificateur de l'application doit tout accepter."""
        if ex is None:
            return None
        answer = json.loads(ex["messages"][2]["content"])
        by_label = {p["label"]: p["texte"] for p in ex["meta"]["rendu"]["passages"]}
        items = answer.get("findings") or answer.get("sentences") or []
        for it in items:
            src = by_label[it["sources"][0]]
            if not contains(src, it["text"]) and not _assembled_ok(src, it["text"]):
                return None
        rep = verify(ex)
        if rep[1] or rep[0] < 1:
            return None
        ex["meta"]["tpv"], ex["meta"]["bloquants"] = rep[0], rep[1]
        return ex


def _assembled_ok(passage: str, text: str) -> bool:
    """Phrase « amorce + alinéa » : les deux morceaux se recopient du passage."""
    flat = re.sub(r"\s+", " ", passage)
    for m in re.finditer(r"\s[a-z]\)\s", " " + flat):
        pass
    parts = re.split(r"(?<=[:])\s+", text, maxsplit=1)
    if len(parts) == 2:
        a, b = parts
        return a.rstrip(":") in flat and b.rstrip(".") in flat
    # amorce sans « : » (jointure par espace) : essayer chaque coupure
    words = text.rstrip(".").split(" ")
    for cut in range(3, len(words) - 2):
        if " ".join(words[:cut]).rstrip(":") in flat and " ".join(words[cut:]) in flat:
            return True
    return False


def verify(example: dict) -> tuple[float, list[str]]:
    r = example["meta"]["rendu"]
    ps = [Passage(label=p["label"], chunk=_chunk(example["meta"]["source"], example["meta"]["id"], i, p["texte"], p["titre"]),
                  score=1.0 / (i + 1), ranks={"bm25": i + 1}) for i, p in enumerate(r["passages"])]
    answer = json.loads(example["messages"][2]["content"])
    if "findings" in answer:
        LLMFindings.model_validate(answer)
        draft = LLMSection.model_validate({"status": "ok", "sentences": [
            {"text": f["text"], "kind": "fact", "sources": f["sources"], "findings": []} for f in answer["findings"]]})
    else:
        draft = LLMSection.model_validate({k: v for k, v in answer.items() if k != "stance"})
    rep = verify_section(resolve_labels(draft, ps, section_key="verif"), {p.chunk.id: p.chunk for p in ps},
                         dossier_id=example["meta"]["id"])
    return rep.tpv, [i.code for i in rep.issues if i.severity == "blocking"]


def load_reports(src_dir: Path) -> list[dict]:
    manifest = json.loads((Path(src_dir) / "eca-manifest.json").read_text("utf-8"))
    out = []
    for row in manifest:
        text = (Path(src_dir) / f"{row['id']}.txt").read_text("utf-8", errors="replace")
        rep = None
        if row.get("reponse"):
            rep = (Path(src_dir) / f"{row['reponse']['id']}.txt").read_text("utf-8", errors="replace")
        title = next((ln.strip() for ln in text.splitlines()[:60] if len(ln.strip()) > 25), row["id"])
        out.append({**row, "text": text, "reply_text": rep, "titre": f"Rapport spécial {row['number']:02d}/{row['year']} : {title}",
                    "reponse": row.get("reponse")})
    return out


def build_report(report: dict, seed: int = 7) -> list[dict]:
    """Tous les exemples candidats d'un rapport (le tirage global est fait ensuite)."""
    rng = random.Random(f"{seed}-{report['id']}")
    b = Builder(report, rng)
    recs = P.recommendations(report["text"])
    paras = P.body_paragraphs(report["text"])
    out: list[dict | None] = []
    for by_year in (False, True):
        out.append(b.roadmap(recs, by_year))
    for k in range(4):
        out.append(b.extraction(paras, None if k % 2 == 0 else (rng.choice(recs) if recs else None)))
    if report["reply_text"]:
        pos = P.positions(report["reply_text"])
        by_n = {r.number: r for r in recs}
        for n, plist in pos.items():
            if n not in by_n:
                continue
            for p in plist:
                out.append(b.stance(by_n[n], p, plist, conflict=False))
                if p.stance != "accept" or rng.random() < 0.25:
                    out.append(b.stance(by_n[n], p, plist, conflict=True))
    for kind in ("echeance", "position", "contrainte"):
        out.append(b.refusal(kind, recs, paras))
        out.append(b.refusal(kind, recs, paras))
    from training.dataset import (
        eca_axes,  # axes : vérité = parties du sommaire du rapport
    )
    out += [e for e in eca_axes.build_examples(report, rng) if not eca_axes.check(e, report["text"])]
    return [e for e in out if e]
