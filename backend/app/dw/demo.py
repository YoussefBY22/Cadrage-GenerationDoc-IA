"""Données de démonstration (07 §9) : un jeu **inventé**, marqué `is_demo`, passant par la vraie chaîne.

Le jeu rejoue le produit : des consultants rédigent avec la configuration de production (recherche
+ modèle de base), soumettent, et des responsables approuvent ou renvoient avec motif (H6, 06 §8).
L'histoire s'arrête à `AS_OF` : il reste donc des brouillons, des livrables en relecture et des
renvois. Aucun banc A/B/C/D n'est inventé : sans résultat réel, il s'affiche « non mesuré ».

Les lignes sont écrites en lot dans les tables opérationnelles, puis l'ETL les charge : la démo
teste aussi le chargement. Toutes les valeurs sont **inventées**, tirées d'une graine fixe.
"""

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import Engine, insert, select

from ..domain.generation import DeliverableContent, SectionDraft, Sentence
from ..ingest.registry import MIME
from ..storage import schema as sc

DEMO_PREFIX = "[DÉMO] "
AS_OF = date(2026, 11, 20)
WEEKS = 38
COUNT_KEYS = ("dossiers", "documents", "chunks", "deliverables", "versions", "transitions", "runs",
              "alerts")

BASE_MODEL = "demo-base-1.7b"
# Production : le service écrit `config_label="default"` (services/generation.py).
PRODUCTION = {"model": BASE_MODEL, "adapter": "DemoProvider", "label": "default", "tpv": 0.82,
              "cite": 0.975, "refusal": 0.05, "latency": 9000, "unchanged": 0.50}
TEMPLATES = {
    "tor": ("tor-fr-standard", ["contexte", "objectifs", "livrables", "calendrier", "profil",
                                "evaluation"]),
    "cdc": ("cdc-fr-standard", ["perimetre", "fonctionnelles", "non_fonctionnelles",
                                "contraintes", "recette"]),
}
# Uniquement des formats que `app/ingest` accepte.
FORMATS = {"pdf": 0.40, "docx": 0.30, "pptx": 0.20, "txt": 0.10}
DELIVERABLES_PER_WEEK = [3, 4, 4, 5, 5, 5, 6, 6]
ABSENCE_DAYS = 24   # scénario : un responsable est absent en fin de période, la file se forme
STALLED_DAYS = 56   # les brouillons en suspens sont récents
REVIEW_REASONS = ["À reprendre : sources à compléter", "À reprendre : chiffres à justifier",
                  "À reprendre : périmètre à préciser", "À reprendre : rédaction à clarifier"]
SUBJECTS = ["Le comité de pilotage", "L'équipe projet", "La direction des opérations",
            "Le service informatique", "Le prestataire retenu", "La maîtrise d'ouvrage",
            "Le dispositif de suivi", "Le périmètre fonctionnel"]
PREDICATES = ["valide chaque étape après relecture des", "documente les exigences liées aux",
              "s'engage à livrer dans les délais prévus les", "met en place un suivi mensuel des",
              "réévalue régulièrement les risques associés aux", "partage avec les parties prenantes les"]
OBJECTS = ["échanges avec les équipes métier", "contraintes budgétaires du programme",
           "indicateurs de performance convenus", "livrables attendus par la direction",
           "dépendances entre les chantiers en cours", "décisions prises lors des ateliers"]


def _lognormal(rng: random.Random, median: float, sigma: float) -> float:
    return rng.lognormvariate(math.log(median), sigma)


def _revise(rng: random.Random, text: str, ratio: float) -> str:
    """Remplace environ `ratio` des mots d'une phrase (similarité proche de 1 - ratio)."""
    words = text.split()
    for i in rng.sample(range(len(words)), min(len(words), max(1, round(ratio * len(words))))):
        words[i] = f"mot{rng.randint(10, 99)}"
    return " ".join(words)


class _Demo:
    def __init__(self, seed: int, clients: int, weeks: int, as_of: date):
        self.rng = random.Random(seed)
        self.clients, self.weeks = clients, weeks
        self.now = datetime.combine(as_of, time(18), tzinfo=UTC)
        self.rows: dict[str, list[dict]] = defaultdict(list)
        self.serial: dict[str, int] = defaultdict(int)
        self.consultants: list[str] = []
        self.reviewers: list[str] = []
        self.other_chunks: list[str] = []

    def _id(self, prefix: str) -> str:
        self.serial[prefix] += 1
        return f"{prefix}_demo{self.serial[prefix]:06d}"

    # --- socle : personnes, dossiers, documents -----------------------------------------------
    def users(self, created: datetime) -> None:
        for role, label, count, bucket in (("consultant", "Consultant", 4, self.consultants),
                                           ("reviewer", "Responsable", 2, self.reviewers)):
            for i in range(1, count + 1):
                uid = self._id("usr")
                bucket.append(uid)
                self.rows["users"].append({
                    "id": uid, "email": f"demo.{label.lower()}{i}@demo.local",
                    "display_name": f"{DEMO_PREFIX}{label} {i}", "password_hash": "!",
                    "role": role, "created_at": created, "active": True})

    def dossier(self, index: int, at: datetime) -> dict:
        rng = self.rng
        dos = self._id("dos")
        owner = self.consultants[index % len(self.consultants)]
        reviewer = rng.choice(self.reviewers)
        self.rows["dossiers"].append({
            "id": dos, "name": f"{DEMO_PREFIX}Mission {index + 1:03d}",
            "client_name": f"Société Démo {rng.randrange(self.clients) + 1}", "sector": None,
            "language": "fr", "owner_id": owner, "created_at": at, "archived": False, "is_demo": True})
        self.rows["dossier_members"] += [
            {"dossier_id": dos, "user_id": owner, "role": "consultant"},
            {"dossier_id": dos, "user_id": reviewer, "role": "reviewer"}]
        chunks: list[str] = []
        for d in range(rng.randint(2, 4)):
            doc = self._id("doc")
            ext = rng.choices(list(FORMATS), weights=list(FORMATS.values()))[0]
            self.rows["documents"].append({
                "id": doc, "dossier_id": dos, "filename": f"demo_{index + 1}_{d + 1}.{ext}",
                "mime": MIME[ext], "sha256": f"{rng.getrandbits(256):064x}", "title": None,
                "language": "fr", "pages": 4, "stored_path": f"/demo/{dos}/{d}", "created_at": at,
                "created_by": owner})
            for k in range(4):
                chk = self._id("chk")
                chunks.append(chk)
                flagged = rng.random() < 0.018
                code = rng.choice(["EXFIL_URL", "ROLE_OVERRIDE"]) if flagged else None
                self.rows["chunks"].append({
                    "id": chk, "document_id": doc, "dossier_id": dos, "ordinal": k,
                    "text": "Extrait fictif de démonstration.", "page_start": k + 1,
                    "page_end": k + 1, "section_path": [], "token_estimate": 6,
                    "injection_flags": [code] if flagged else []})
                if flagged:
                    self.rows["injection_alerts"].append({
                        "id": self._id("alr"), "chunk_id": chk, "dossier_id": dos,
                        "codes": [code], "created_at": at})
        self.rows["generation_runs"].append(self.run_row(
            dos, None, None, "findings", "ok", at + timedelta(minutes=5), rng.randint(300, 900)))
        info = {"id": dos, "owner": owner, "reviewer": reviewer, "chunks": chunks,
                "others": self.other_chunks[-200:]}
        self.other_chunks += chunks
        return info

    def run_row(self, dos, dlv, key, kind, status, at, tokens_out) -> dict:
        rng = self.rng
        factor = 1.5 if kind == "findings" else 1.0
        return {"id": self._id("run"), "dossier_id": dos, "deliverable_id": dlv, "section_key": key,
                "kind": kind, "provider": "demo", "model": PRODUCTION["model"],
                "adapter": PRODUCTION["adapter"], "config_label": PRODUCTION["label"],
                "status": status, "attempts": 2 if rng.random() < 0.1 else 1,
                "latency_ms": int(_lognormal(rng, PRODUCTION["latency"] * factor, 0.35)),
                "tokens_in": rng.randint(1800, 3500), "tokens_out": tokens_out, "started_at": at}

    # --- une section générée : phrases, citations, vérification --------------------------------
    def section(self, dos: dict, dlv: str, key: str, at: datetime) -> tuple[SectionDraft, set[int]]:
        """Renvoie la section et les positions des phrases bloquantes."""
        rng = self.rng
        refused = rng.random() < PRODUCTION["refusal"]
        n = 0 if refused else rng.randint(4, 8)
        run = self.run_row(dos["id"], dlv, key, "section", "refused" if refused else "ok", at, n * 48)
        self.rows["generation_runs"].append(run)
        if refused:
            return SectionDraft(section_key=key, status="insufficient_evidence", sentences=[],
                                missing_evidence="Éléments insuffisants (démo)"), set()
        for rank, chk in enumerate(rng.sample(dos["chunks"], min(len(dos["chunks"]), 4)), 1):
            self.rows["retrieval_hits"].append({"run_id": run["id"], "label": f"P{rank}",
                                                "chunk_id": chk, "rank": rank, "score": 1.0 / rank})
        sentences, blocking = [], set()
        for i in range(n):
            issues = []
            if rng.random() < PRODUCTION["cite"]:
                source = rng.choice(dos["chunks"])
            elif dos["others"] and rng.random() < 0.4:
                source, issue = rng.choice(dos["others"]), "FOREIGN_SOURCE"
                issues.append(issue)
            else:
                source = f"chk_inconnu_{rng.randint(1, 99)}"
                issues.append("UNKNOWN_SOURCE")
            cited = rng.randint(1, 2) if rng.random() < 0.4 else 0
            found, draw = cited, rng.random()
            if issues:
                status, support = "failed", rng.uniform(0.05, 0.35)
            elif draw < PRODUCTION["tpv"] / PRODUCTION["cite"]:
                status, support = "verified", rng.uniform(0.75, 0.98)
            elif rng.random() < 0.65:
                status, support = "warning", rng.uniform(0.4, 0.7)
                issues.append("LOW_SUPPORT")
            else:
                status, support = "failed", rng.uniform(0.05, 0.35)
                found = max(cited - 1, 0)
                issues.append("NUMBER_NOT_FOUND" if cited > found else "FACT_WITHOUT_SOURCE")
            if status == "failed":
                blocking.add(i)
            self.rows["verification_results"].append({
                "run_id": run["id"], "sentence_index": i, "status": status, "numbers_cited": cited,
                "numbers_found": found, "support": round(support, 3),
                "issues": [{"sentence_index": i, "code": c, "detail": "démo",
                            "severity": "warning" if c == "LOW_SUPPORT" else "blocking"}
                           for c in issues]})
            text = (f"{rng.choice(SUBJECTS)} {rng.choice(PREDICATES)} {rng.choice(OBJECTS)} "
                    f"({rng.randint(2, 90)} points).")
            sentences.append(Sentence(text=text, kind="fact", source_ids=[source]))
        return SectionDraft(section_key=key, status="ok", sentences=sentences), blocking

    # --- relecture humaine d'un contenu --------------------------------------------------------
    def edit(self, dos: dict, drafts: list[SectionDraft], blocking: list[set[int]],
             fix_probability: float, polish: bool) -> tuple[list[SectionDraft], list[set[int]]]:
        rng = self.rng
        out, left = [], []
        for sec, bad in zip(drafts, blocking, strict=True):
            ratio = (0.0 if not polish or rng.random() < PRODUCTION["unchanged"]
                     else rng.betavariate(2, 5))
            sentences, remaining = [], set()
            for i, s in enumerate(sec.sentences):
                if i in bad:
                    # une source absente est toujours corrigée : la démo n'invente pas d'approbation sans source
                    absent = s.source_ids[0] not in dos["chunks"]
                    if rng.random() < (0.96 if absent else fix_probability):
                        s = s.model_copy(update={"text": _revise(rng, s.text, 0.4),
                                                 "source_ids": [rng.choice(dos["chunks"])]})
                    elif absent:  # hors du tirage principal : le scénario reste le même
                        fix = random.Random(s.text)
                        s = s.model_copy(update={"text": _revise(fix, s.text, 0.4),
                                                 "source_ids": [fix.choice(dos["chunks"])]})
                    else:
                        remaining.add(i)
                elif ratio:
                    s = s.model_copy(update={"text": _revise(rng, s.text, ratio)})
                sentences.append(s)
            out.append(sec.model_copy(update={"sentences": sentences}))
            left.append(remaining)
        return out, left

    # --- la vie d'un livrable, coupée à `now` --------------------------------------------------
    def deliverable(self, dos: dict, kind: str, created: datetime) -> None:
        rng = self.rng
        template, keys = TEMPLATES[kind]
        dlv, author = self._id("dlv"), dos["owner"]
        row = {"id": dlv, "dossier_id": dos["id"], "type": kind, "template_id": template,
               "state": "draft", "current_version": 0, "author_id": author,
               "created_at": created, "updated_at": created}
        self.rows["deliverables"].append(row)

        def version(sections: list[SectionDraft], origin: str, at: datetime) -> None:
            content = DeliverableContent(type=kind, language="fr", template_id=template,
                                         template_version="1.0", sections=sections
                                         ).model_dump(mode="json")
            row["current_version"] += 1
            row["updated_at"] = at
            self.rows["deliverable_versions"].append({
                "deliverable_id": dlv, "version": row["current_version"], "content": content,
                "origin": origin, "author_id": author, "created_at": at,
                "content_sha256": hashlib.sha256(
                    json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})

        def move(to: str, at: datetime, user: str, reason: str | None = None) -> None:
            self.rows["state_transitions"].append({
                "id": self._id("trn"), "deliverable_id": dlv, "version": row["current_version"],
                "from_state": row["state"], "to_state": to, "user_id": user, "reason": reason,
                "at": at})
            row["state"], row["updated_at"] = to, at

        generated = [self.section(dos, dlv, key, created + timedelta(minutes=2 + 3 * k))
                     for k, key in enumerate(keys)]
        drafts, blocking = [g[0] for g in generated], [g[1] for g in generated]
        version(drafts, "generated", created + timedelta(minutes=3 * len(keys) + 5))
        if rng.random() < 0.10 and created > self.now - timedelta(days=STALLED_DAYS):
            return                                                  # brouillon laissé en suspens
        edited_at = created + timedelta(hours=_lognormal(rng, 20, 0.7))
        if edited_at > self.now:
            return
        drafts, blocking = self.edit(dos, drafts, blocking, 0.72, polish=True)
        version(drafts, "edited", edited_at)
        t = edited_at + timedelta(hours=_lognormal(rng, 5, 0.8))
        for attempt in range(3):
            if t > self.now:
                return
            move("in_review", t, author)
            slow = rng.random() < 0.10
            t += timedelta(hours=_lognormal(rng, 120 if slow else 22, 0.6))
            away = (dos["reviewer"] == self.reviewers[-1]
                    and t > self.now - timedelta(days=ABSENCE_DAYS))
            if t > self.now or away:
                return
            fragile = any(blocking)
            p_reject = (0.48 if fragile else 0.09) if attempt == 0 else (0.15 if fragile else 0.03)
            if attempt == 2 or rng.random() >= p_reject:
                # l'approbation exige d'acquitter chaque phrase bloquante (workflow/state_machine.py)
                for key, left in zip(keys, blocking, strict=True):
                    for i in sorted(left):
                        self.rows["audit_log"].append({
                            "at": t, "user_id": dos["reviewer"], "action": "sentence.acknowledge",
                            "object_type": "deliverable", "object_id": dlv,
                            "details": {"version": row["current_version"], "section_key": key,
                                        "sentence_index": i}})
                move("approved", t, dos["reviewer"], "ok")
                return
            reason = rng.choices(REVIEW_REASONS, weights=[5, 3, 2, 2] if fragile else [1, 1, 4, 3])[0]
            move("rejected", t, dos["reviewer"], reason)
            if t > self.now - timedelta(days=STALLED_DAYS) and rng.random() < 0.45:
                return                                              # renvoi pas encore repris
            t += timedelta(hours=_lognormal(rng, 30, 0.6))
            if t > self.now:
                return
            move("draft", t, author)
            t += timedelta(hours=_lognormal(rng, 14, 0.6))
            if t > self.now:
                return
            drafts, blocking = self.edit(dos, drafts, blocking, 0.9, polish=False)
            version(drafts, "edited", t)
            t += timedelta(hours=1)

    def build(self) -> dict[str, list[dict]]:
        rng = self.rng
        start = self.now - timedelta(days=7 * self.weeks)
        self.users(start)
        index = 0
        for week in range(self.weeks):
            opens = start + timedelta(days=7 * week)
            remaining = rng.choice(DELIVERABLES_PER_WEEK)
            while remaining:
                at = opens + timedelta(hours=rng.uniform(1, 160))
                dos = self.dossier(index, at)
                index += 1
                kinds = ["tor", "cdc"] if remaining > 1 and rng.random() < 0.4 else [
                    rng.choices(["tor", "cdc"], weights=[2, 1])[0]]
                for k, kind in enumerate(kinds):
                    self.deliverable(dos, kind, at + timedelta(minutes=20 + 45 * k))
                remaining -= len(kinds)
        return self.rows


def generate_demo(op_engine: Engine, *, seed: int = 42, clients: int = 5, weeks: int = WEEKS,
                  as_of: date = AS_OF) -> dict[str, int]:
    """Crée le jeu de démonstration, charge l'entrepôt et crée les vues ; renvoie les comptes.

    Sans effet (comptes à zéro) si des dossiers de démonstration existent déjà.
    """
    from .etl import run_etl
    from .views_sql import create_views

    with op_engine.connect() as c:
        if c.execute(select(sc.dossiers.c.id).where(sc.dossiers.c.is_demo.is_(True))).first():
            return dict.fromkeys(COUNT_KEYS, 0)
    demo = _Demo(seed, clients, weeks, as_of)
    rows = demo.build()
    with op_engine.begin() as c:
        for table in sc.metadata.sorted_tables:
            data = rows.get(table.name, [])
            for i in range(0, len(data), 400):
                c.execute(insert(table), data[i:i + 400])
    loaded = run_etl(op_engine, op_engine, full=True, now=demo.now)
    create_views(op_engine)
    names = {"versions": "deliverable_versions", "transitions": "state_transitions",
             "runs": "generation_runs", "alerts": "injection_alerts"}
    counts = {k: len(rows.get(names.get(k, k), [])) for k in COUNT_KEYS}
    counts["dw_rows"] = sum(loaded.values())
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère le jeu de démonstration (valeurs inventées)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clients", type=int, default=5)
    parser.add_argument("--weeks", type=int, default=WEEKS)
    args = parser.parse_args()
    from ..config import get_settings
    from ..storage.engine import make_engine

    engine = make_engine(get_settings().storage_url)
    if engine.dialect.name == "sqlite":
        sc.metadata.create_all(engine)
    print(json.dumps(generate_demo(engine, seed=args.seed, clients=args.clients, weeks=args.weeks)))


if __name__ == "__main__":
    main()
