"""Données de démonstration (07 §9) : un jeu **inventé**, marqué `is_demo`, passant par la vraie chaîne.

Les lignes sont écrites dans les tables opérationnelles via `SqlRepository` (dossiers « [DÉMO] … »),
puis l'ETL les charge dans `dw` : la démonstration teste aussi le chargement. Toutes les valeurs
(TPV, latences, refus, retouches) sont des **valeurs inventées** tirées d'une graine fixe.
"""

import argparse
import json
import math
import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Engine, bindparam, select, update

from ..domain.documents import Block, Chunk, ParsedDocument
from ..domain.generation import DeliverableContent, SectionDraft, Sentence
from ..domain.retrieval import Passage
from ..domain.verification import Issue, SentenceCheck, VerificationReport
from ..storage import schema as sc
from ..storage.sql_repository import SqlRepository

DEMO_PREFIX = "[DÉMO] "

# Distributions inventées (07 §9) : TPV moyen, citations valides, médiane de latence (ms),
# part de refus, part de sections acceptées sans modification, poids de tirage de la configuration.
CONFIGS = {
    "A": {"model": "demo-petit-7b", "tpv": 0.35, "cite": 0.85, "latency": 4000, "refusal": 0.05,
          "unchanged": 0.05, "weight": 0.15},
    "B": {"model": "demo-instruct-8b", "tpv": 0.82, "cite": 0.97, "latency": 9000, "refusal": 0.08,
          "unchanged": 0.30, "weight": 0.40},
    "C": {"model": "demo-instruct-14b", "tpv": 0.86, "cite": 0.98, "latency": 14000, "refusal": 0.05,
          "unchanged": 0.35, "weight": 0.25},
    "D": {"model": "demo-lora-8b", "tpv": 0.78, "cite": 0.96, "latency": 9500, "refusal": 0.06,
          "unchanged": 0.25, "weight": 0.20},
}
TEMPLATES = {
    "tor": ("tor-fr-standard", ["contexte", "objectifs", "livrables", "calendrier", "profil",
                                "evaluation"]),
    "cdc": ("cdc-fr-standard", ["perimetre", "fonctionnelles", "non_fonctionnelles",
                                "contraintes", "recette"]),
}
MIMES = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         "text/plain", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
SUBJECTS = ["Le comité de pilotage", "L'équipe projet", "La direction des opérations",
            "Le service informatique", "Le prestataire retenu", "La maîtrise d'ouvrage",
            "Le dispositif de suivi", "Le périmètre fonctionnel"]
PREDICATES = ["valide chaque étape après relecture des", "documente les exigences liées aux",
              "s'engage à livrer dans les délais prévus les", "met en place un suivi mensuel des",
              "réévalue régulièrement les risques associés aux", "partage avec les parties prenantes les"]
OBJECTS = ["échanges avec les équipes métier", "contraintes budgétaires du programme",
           "indicateurs de performance convenus", "livrables attendus par la direction",
           "dépendances entre les chantiers en cours", "décisions prises lors des ateliers"]
REVIEW_REASONS = ["À reprendre : sources à compléter", "À reprendre : chiffres à justifier"]


def _pick(rng: random.Random, seq):
    return seq[rng.randrange(len(seq))]


def _sentence(rng: random.Random) -> str:
    return f"{_pick(rng, SUBJECTS)} {_pick(rng, PREDICATES)} {_pick(rng, OBJECTS)} ({rng.randint(2, 90)} points)."


def _revise(rng: random.Random, text: str, ratio: float) -> str:
    """Remplace environ `ratio` des mots d'une phrase (le rapport de similarité reste proche de 1 - ratio)."""
    words = text.split()
    n = min(len(words), round(ratio * len(words)))
    for i in rng.sample(range(len(words)), n):
        words[i] = f"mot{rng.randint(10, 99)}"
    return " ".join(words)


def _choose_config(rng: random.Random) -> str:
    x, acc = rng.random(), 0.0
    for label, c in CONFIGS.items():
        acc += c["weight"]
        if x < acc:
            return label
    return "B"


def _at(day: date, minutes: float) -> datetime:
    return datetime(day.year, day.month, day.day, 8, 0, tzinfo=UTC) + timedelta(minutes=minutes)


class _Demo:
    def __init__(self, engine: Engine, seed: int, clients: int, missions: int, days: int, start: date):
        self.engine, self.repo = engine, SqlRepository(engine)
        self.rng = random.Random(seed)
        self.clients, self.missions, self.days, self.start = clients, missions, days, start
        self.counts = dict.fromkeys(
            ("dossiers", "documents", "chunks", "deliverables", "versions", "transitions", "runs",
             "alerts"), 0)
        self.chunks: dict[str, list[Chunk]] = {}
        self.dos_created: dict[str, datetime] = {}
        self.dlv_created: dict[str, datetime] = {}
        self.version_times: dict[tuple[str, int], datetime] = {}
        self.transition_times: dict[str, list[datetime]] = {}
        self.run_no = 0
        self.carry = dict.fromkeys(CONFIGS, 0.5)
        from ..config import get_settings
        self.dim = get_settings().embedding_dim

    # --- socle : utilisateurs, dossiers, documents -------------------------------------------
    def users(self) -> tuple[list[str], str]:
        authors = [self.repo.create_user(f"demo.consultant{i}@demo.local", f"{DEMO_PREFIX}Consultant {i}",
                                         "!", "consultant") for i in (1, 2, 3)]
        reviewer = self.repo.create_user("demo.relecteur@demo.local", f"{DEMO_PREFIX}Relecteur", "!",
                                         "admin")
        return authors, reviewer

    def dossier(self, index: int, owner: str) -> tuple[str, date]:
        rng = self.rng
        client = f"Société Démo {index % self.clients + 1}"
        dos = self.repo.create_dossier(f"{DEMO_PREFIX}Mission {index + 1}", client, "fr", owner)
        day = self.start + timedelta(days=rng.randint(0, max(self.days - 14, 1)))
        self.dos_created[dos] = _at(day, 0)
        self.counts["dossiers"] += 1
        chunks: list[Chunk] = []
        for d in range(rng.randint(2, 4)):
            sha = f"{rng.getrandbits(256):064x}"
            parsed = ParsedDocument(filename=f"demo_{index + 1}_{d + 1}.dat", mime=_pick(rng, MIMES),
                                    sha256=sha, title=None, language="fr", blocks=[Block(text="x", page=1)])
            doc = self.repo.add_document(dos, parsed, f"/demo/{dos}/{d}")
            doc_chunks = [Chunk(id=f"chk_demo{index}_{d}_{k}", document_id=doc, dossier_id=dos,
                                ordinal=k, text="Extrait fictif de démonstration.", page_start=k + 1,
                                page_end=k + 1, section_path=(), token_estimate=6) for k in range(4)]
            vectors = [[rng.random() for _ in range(self.dim)] for _ in doc_chunks]
            self.repo.add_chunks(doc_chunks, vectors, "demo")
            for ch in doc_chunks:
                if rng.random() < 0.06:
                    self.repo.record_alert(ch.id, [_pick(rng, ["EXFIL_URL", "ROLE_OVERRIDE"])])
                    self.counts["alerts"] += 1
            chunks += doc_chunks
            self.counts["documents"] += 1
            self.counts["chunks"] += len(doc_chunks)
        self.chunks[dos] = chunks
        return dos, day

    # --- une section : run, phrases, vérification ---------------------------------------------
    def section(self, dos: str, dlv: str, key: str, when: datetime, others: list[Chunk]):
        rng = self.rng
        cfg_label = _choose_config(rng)
        cfg = CONFIGS[cfg_label]
        refused = rng.random() < cfg["refusal"]
        n = 0 if refused else rng.randint(4, 8)
        latency = int(rng.lognormvariate(math.log(cfg["latency"]), 0.4))
        self.run_no += 1
        run_id = f"run_demo_{self.run_no}"
        self.repo.record_run({
            "id": run_id, "dossier_id": dos, "deliverable_id": dlv, "section_key": key,
            "kind": "section", "provider": "demo", "model": cfg["model"], "adapter": "demo",
            "config_label": cfg_label, "status": "refused" if refused else "ok",
            "attempts": 2 if rng.random() < 0.1 else 1, "latency_ms": latency,
            "tokens_in": rng.randint(1800, 3500), "tokens_out": n * rng.randint(35, 60),
            "started_at": when})
        self.counts["runs"] += 1
        if refused:
            return SectionDraft(section_key=key, status="insufficient_evidence", sentences=[],
                                missing_evidence="Éléments insuffisants (démo)"), cfg_label
        own = self.chunks[dos]
        passages = rng.sample(own, min(len(own), 4))
        self.repo.record_retrieval(run_id, [Passage(label=f"P{i}", chunk=c, score=1 / i, ranks={})
                                            for i, c in enumerate(passages, 1)])
        sentences, checks, issues = [], [], []
        for i in range(n):
            if rng.random() < cfg["cite"]:
                source = _pick(rng, own).id
            elif rng.random() < 0.5:
                source = _pick(rng, others).id if others else "chk_inconnu"
            else:
                source = f"chk_inconnu_{rng.randint(1, 99)}"
            sentences.append(Sentence(text=_sentence(rng), kind="fact", source_ids=[source]))
            cited = rng.randint(1, 2) if rng.random() < 0.4 else 0
            # diffusion d'erreur : la part cumulée de phrases vérifiées suit exactement le TPV cible
            self.carry[cfg_label] += cfg["tpv"]
            ok = self.carry[cfg_label] >= 1
            self.carry[cfg_label] -= 1 if ok else 0
            if ok:
                status, support, found = "verified", rng.uniform(0.75, 0.98), cited
            elif rng.random() < 0.6:
                status, support, found = "warning", rng.uniform(0.4, 0.7), cited
                issues.append(Issue(sentence_index=i, code="LOW_SUPPORT", severity="warning",
                                    detail="appui lexical faible"))
            else:
                status, support, found = "failed", rng.uniform(0.05, 0.35), max(cited - 1, 0)
                code = "NUMBER_NOT_FOUND" if cited > found else "FACT_WITHOUT_SOURCE"
                issues.append(Issue(sentence_index=i, code=code, severity="blocking", detail="démo"))
            checks.append(SentenceCheck(index=i, status=status, numbers_cited=cited,
                                        numbers_found=found, support=round(support, 3)))
        self.repo.record_verification(run_id, VerificationReport(
            section_key=key, checks=checks, issues=issues))
        return SectionDraft(section_key=key, status="ok", sentences=sentences), cfg_label

    # --- un livrable : sections, versions, relecture ------------------------------------------
    def deliverable(self, dos: str, day: date, dtype: str, author: str, reviewer: str,
                    others: list[Chunk]) -> None:
        rng = self.rng
        template, keys = TEMPLATES[dtype]
        dlv = self.repo.create_deliverable(dos, dtype, template, author)
        t0 = _at(day, 20 + rng.randint(0, 600))
        self.dlv_created[dlv] = t0
        self.counts["deliverables"] += 1
        drafts: list[SectionDraft] = []
        labels: dict[str, str] = {}
        for k, key in enumerate(keys):
            draft, labels[key] = self.section(dos, dlv, key, t0 + timedelta(minutes=2 + 3 * k),
                                              others)
            drafts.append(draft)
        content = DeliverableContent(type=dtype, language="fr", template_id=template,
                                     template_version="1.0", sections=drafts)
        t_gen = t0 + timedelta(minutes=3 * len(keys) + 5)
        v = self.repo.add_version(dlv, content, author, "generated")
        self.version_times[(dlv, v)] = t_gen
        self.counts["versions"] += 1

        fate = rng.random()
        if fate < 0.07:
            return                                          # reste en brouillon
        times = self.transition_times.setdefault(dlv, [])

        def move(state: str, at: datetime, reason: str | None = None, user: str = author) -> None:
            self.repo.set_state(dlv, state, user, reason)
            times.append(at)
            self.counts["transitions"] += 1

        def edit(at: datetime) -> None:
            sections = []
            for d in drafts:
                ratio = 0.0 if rng.random() < CONFIGS[labels[d.section_key]]["unchanged"] \
                    else rng.betavariate(2, 5)
                sections.append(d.model_copy(update={"sentences": [
                    s.model_copy(update={"text": _revise(rng, s.text, ratio)}) for s in d.sentences]}))
            final = content.model_copy(update={"sections": sections})
            ver = self.repo.add_version(dlv, final, author, "edited")
            self.version_times[(dlv, ver)] = at
            self.counts["versions"] += 1

        t = t_gen + timedelta(hours=rng.uniform(0.5, 4))
        move("in_review", t)
        if fate < 0.15:
            return                                          # encore en relecture
        if rng.random() < 0.15:                             # refusé une fois en relecture
            t += timedelta(hours=rng.lognormvariate(math.log(8), 0.5))
            move("rejected", t, _pick(rng, REVIEW_REASONS), reviewer)
            t += timedelta(hours=rng.uniform(1, 6))
            edit(t - timedelta(minutes=5))
            move("in_review", t)
        else:
            edit(t + timedelta(minutes=5))
        t += timedelta(hours=rng.lognormvariate(math.log(6), 0.6))
        move("approved", t, "ok", reviewer)

    def findings_run(self, dos: str, day: date) -> None:
        rng = self.rng
        label = _choose_config(rng)
        cfg = CONFIGS[label]
        self.run_no += 1
        self.repo.record_run({
            "id": f"run_demo_{self.run_no}", "dossier_id": dos, "kind": "findings", "provider": "demo",
            "model": cfg["model"], "adapter": "demo", "config_label": label, "status": "ok",
            "attempts": 1, "latency_ms": int(rng.lognormvariate(math.log(cfg["latency"] * 1.5), 0.4)),
            "tokens_in": rng.randint(3000, 6000), "tokens_out": rng.randint(300, 900),
            "started_at": _at(day, 5)})
        self.counts["runs"] += 1

    # --- horodatage déterministe (les dépôts datent « maintenant ») --------------------------
    def stamp(self) -> None:
        with self.engine.begin() as c:
            for dos, at in self.dos_created.items():
                c.execute(update(sc.dossiers).where(sc.dossiers.c.id == dos).values(
                    created_at=at, is_demo=True))
            for dlv, at in self.dlv_created.items():
                c.execute(update(sc.deliverables).where(sc.deliverables.c.id == dlv).values(
                    created_at=at))
            for (dlv, version), at in self.version_times.items():
                c.execute(update(sc.deliverable_versions).where(
                    sc.deliverable_versions.c.deliverable_id == dlv,
                    sc.deliverable_versions.c.version == version).values(created_at=at))
            for dlv, times in self.transition_times.items():
                rows = c.execute(select(sc.state_transitions.c.id).where(
                    sc.state_transitions.c.deliverable_id == dlv).order_by(
                    sc.state_transitions.c.at, sc.state_transitions.c.id)).all()
                for (tid,), at in zip(rows, times, strict=True):
                    c.execute(update(sc.state_transitions).where(
                        sc.state_transitions.c.id == bindparam("t")).values(at=at), {"t": tid})

    def run(self) -> dict[str, int]:
        authors, reviewer = self.users()
        # le relecteur possède aussi des dossiers : l'ETL ne marque « démo » que les utilisateurs propriétaires
        owners = [*authors, reviewer]
        made = [self.dossier(i, owners[i % len(owners)]) for i in range(self.missions)]
        for i, (dos, day) in enumerate(made):
            others = [c for d, cs in self.chunks.items() if d != dos for c in cs]
            self.findings_run(dos, day)
            kinds = ["tor"] + (["cdc"] if self.rng.random() < 0.6 else [])
            for kind in kinds:
                self.deliverable(dos, day, kind, authors[i % len(authors)], reviewer, others)
        self.stamp()
        return self.counts


def generate_demo(op_engine: Engine, *, seed: int = 42, clients: int = 5, missions: int = 12,
                  days: int = 90, start: date = date(2026, 9, 1)) -> dict[str, int]:
    """Crée le jeu de démonstration, charge l'entrepôt et crée les vues ; renvoie les comptes.

    Sans effet (comptes à zéro) si des dossiers de démonstration existent déjà.
    """
    from .etl import run_etl
    from .views_sql import create_views

    with op_engine.connect() as c:
        present = c.execute(select(sc.dossiers.c.id).where(sc.dossiers.c.is_demo.is_(True))
                            ).first()
    if present:
        return dict.fromkeys(("dossiers", "documents", "chunks", "deliverables", "versions",
                              "transitions", "runs", "alerts"), 0)
    counts = _Demo(op_engine, seed, clients, missions, days, start).run()
    loaded = run_etl(op_engine, op_engine, full=True)
    create_views(op_engine)
    counts["dw_rows"] = sum(loaded.values())
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère le jeu de démonstration (valeurs inventées)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--missions", type=int, default=12)
    parser.add_argument("--clients", type=int, default=5)
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    from ..config import get_settings
    from ..storage.engine import make_engine

    engine = make_engine(get_settings().storage_url)
    if engine.dialect.name == "sqlite":
        sc.metadata.create_all(engine)
    print(json.dumps(generate_demo(engine, seed=args.seed, missions=args.missions,
                                   clients=args.clients, days=args.days)))


if __name__ == "__main__":
    main()
