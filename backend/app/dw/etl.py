"""Chargement de l'entrepôt (07 §3) : ETL incrémental, idempotent, sans texte client.

    python -m app.dw.etl [--full]

Lit les tables opérationnelles (`app.storage.schema`), écrit dans le schéma `dw`.
Idempotence : clés naturelles (`run_id`, `transition_id`, `(deliverable_id, version, section)`)
+ `ON CONFLICT DO NOTHING` ; les lignes dépendantes (citations, appels) ne sont écrites qu'avec
leur génération. Filigranes : `generation_runs.started_at`, `state_transitions.at`,
`deliverable_versions.created_at`, avec une fenêtre de sécurité de 5 minutes.
"""

import argparse
import difflib
import hashlib
import json
import logging
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import get_args

from sqlalchemy import Engine, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..domain.verification import IssueCode
from ..storage import schema as op
from . import schema as dw
from . import snapshot
from .schema import bind_dw, create_dw

log = logging.getLogger("app.dw")

SAFETY_WINDOW = timedelta(minutes=5)
DEFAULT_BASELINE_MINUTES = 30.0  # hypothèse à faire valider (07 §5) : temps manuel par section
DATE_START, DATE_END = date(2025, 1, 1), date(2028, 12, 31)

TYPES = {"findings": (1, "Constats", "Findings"), "roadmap": (2, "Feuille de route", "Roadmap"),
         "tor": (3, "Termes de référence", "Terms of reference"),
         "cdc": (4, "Cahier des charges", "Specification")}
STATES = {"draft": (1, "Brouillon", 1), "in_review": (2, "En relecture", 2),
          "approved": (3, "Approuvé", 3), "rejected": (4, "Rejeté", 3)}
ISSUE_SEVERITY = {"LOW_SUPPORT": "warning", "TRANSITION_WITH_NUMBER": "warning"}
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre"]
SOURCE_ISSUES = {"UNKNOWN_SOURCE", "FOREIGN_SOURCE"}
BENCH_LABELS = {"A", "B", "C", "D"}  # le service écrit « default » en production


# --- utilitaires ---------------------------------------------------------------------------
def _utc(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


def _date_key(d: datetime) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def _bind_dt(engine: Engine, d: datetime) -> datetime:
    """SQLite stocke des dates naïves (UTC) ; PostgreSQL des dates avec fuseau."""
    return d.replace(tzinfo=None) if engine.dialect.name == "sqlite" else d


def _hours(a: datetime, b: datetime) -> float:
    return round(max((a - b).total_seconds(), 0.0) / 3600.0, 2)


def _batches(seq, n=500):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _insert(c, table, rows: list[dict]) -> None:
    """INSERT … ON CONFLICT DO NOTHING (SQLite et PostgreSQL), sinon INSERT simple."""
    if not rows:
        return
    name = c.dialect.name
    if name == "sqlite":
        stmt = sqlite_insert(table).on_conflict_do_nothing()
    elif name == "postgresql":
        stmt = pg_insert(table).on_conflict_do_nothing()
    else:
        stmt = insert(table)
    for chunk in _batches(rows, 200):
        c.execute(stmt, chunk)


def _words(section: dict | None) -> list[str]:
    if not section:
        return []
    return " ".join(s.get("text", "") for s in section.get("sentences", [])).split()


# --- chargement ----------------------------------------------------------------------------
class _Loader:
    def __init__(self, op_engine: Engine, dw_engine: Engine, full: bool, now: datetime,
                 pseudonymize: bool, as_of: datetime | None = None):
        self.ope, self.dwe, self.full, self.now = op_engine, bind_dw(dw_engine), full, now
        self.as_of = as_of
        self.pseudo = pseudonymize
        self.counts: dict[str, int] = defaultdict(int)
        self.wm: dict[str, str] = {}

    # --- filigranes
    def _since(self, c, source: str) -> datetime | None:
        if self.full:
            return None
        row = c.execute(select(dw.etl_watermark.c.last_value).where(
            dw.etl_watermark.c.source_table == source)).scalar()
        return _utc(datetime.fromisoformat(row)) - SAFETY_WINDOW if row else None

    def _bump(self, source: str, values) -> None:
        vals = [_utc(v) for v in values if v is not None]
        if vals:
            self.wm[source] = max(vals).isoformat()

    # --- dimensions statiques
    def static_dims(self, c) -> None:
        if c.execute(select(func.count()).select_from(dw.dim_date)).scalar() == 0:
            rows, d = [], DATE_START
            while d <= DATE_END:
                rows.append({
                    "date_key": d.year * 10000 + d.month * 100 + d.day, "date": d.isoformat(),
                    "year": d.year, "quarter": (d.month - 1) // 3 + 1, "month": d.month,
                    "month_name_fr": MONTHS_FR[d.month - 1], "iso_week": d.isocalendar()[1],
                    "day_of_week": d.isoweekday(), "is_weekend": d.isoweekday() >= 6})
                d += timedelta(days=1)
            _insert(c, dw.dim_date, rows)
            self.counts["dim_date"] += len(rows)
        _insert(c, dw.dim_deliverable_type, [
            {"type_key": k, "type_code": code, "label_fr": fr, "label_en": en}
            for code, (k, fr, en) in TYPES.items()])
        _insert(c, dw.dim_state, [{"state_key": k, "state_code": code, "label_fr": fr, "step_order": o}
                                  for code, (k, fr, o) in STATES.items()])
        issues = [("NONE", "none", "Aucune anomalie")] + [
            (code, ISSUE_SEVERITY.get(code, "blocking"), code) for code in get_args(IssueCode)]
        _insert(c, dw.dim_issue, [{"issue_key": i, "issue_code": code, "severity": sev, "label_fr": lab}
                                  for i, (code, sev, lab) in enumerate(issues)])
        self.sections: dict[tuple[str, str], tuple[int, float]] = {}
        self._load_sections(c)
        from ..generation.template_loader import load_template
        for code in TYPES:
            try:
                tpl = load_template(code, "fr")
            except Exception:  # noqa: BLE001 — gabarit absent : la section sera créée à la demande
                log.warning("gabarit indisponible", extra={"type": code})
                continue
            for sp in tpl.sections:
                self.section(c, tpl.id, sp.key, code, sp.title)

    def _load_sections(self, c) -> None:
        for r in c.execute(select(dw.dim_section)):
            self.sections[(r.template_id, r.section_code)] = (r.section_key, r.baseline_minutes)

    def section(self, c, template_id: str, code: str, type_code: str,
                title: str | None = None) -> tuple[int, float]:
        found = self.sections.get((template_id, code))
        if found:
            return found
        c.execute(insert(dw.dim_section).values(
            type_key=TYPES[type_code][0], template_id=template_id, section_code=code,
            title_fr=(title or code)[:200], baseline_minutes=DEFAULT_BASELINE_MINUTES))
        self.counts["dim_section"] += 1
        key = c.execute(select(dw.dim_section.c.section_key).where(
            dw.dim_section.c.template_id == template_id,
            dw.dim_section.c.section_code == code)).scalar()
        self.sections[(template_id, code)] = (key, DEFAULT_BASELINE_MINUTES)
        return self.sections[(template_id, code)]

    # --- dimensions de référence
    def reference_dims(self, c, o) -> None:
        self.dossiers = {r.id: r for r in o.execute(select(op.dossiers))}
        users = list(o.execute(select(op.users)))
        involved = defaultdict(list)     # une personne est « démo » si tous ses dossiers le sont
        for d in self.dossiers.values():
            involved[d.owner_id].append(bool(d.is_demo))
        for m in o.execute(select(op.dossier_members)):
            if m.dossier_id in self.dossiers:
                involved[m.user_id].append(bool(self.dossiers[m.dossier_id].is_demo))
        self.op_users = {u.id: u for u in users}
        self.client_keys: dict[str, int] = {r.client_ref: r.client_key
                                            for r in c.execute(select(dw.dim_client))}
        self.mission_keys: dict[str, int] = {}
        self.client_keys_by_dossier: dict[str, int] = {}
        for d in sorted(self.dossiers.values(), key=lambda r: (str(r.created_at), r.id)):
            ref = hashlib.sha256(d.client_name.encode()).hexdigest()
            if ref not in self.client_keys:
                c.execute(insert(dw.dim_client).values(
                    client_ref=ref, client_name="", sector=d.sector, is_demo=bool(d.is_demo)))
                self.client_keys[ref] = c.execute(select(dw.dim_client.c.client_key).where(
                    dw.dim_client.c.client_ref == ref)).scalar()
                self.counts["dim_client"] += 1
            ck = self.client_keys[ref]
            self.client_keys_by_dossier[d.id] = ck
            c.execute(update(dw.dim_client).where(dw.dim_client.c.client_key == ck).values(
                client_name=f"Client {ck:03d}" if self.pseudo else d.client_name[:200],
                sector=d.sector, is_demo=bool(d.is_demo)))
            created = _utc(d.created_at)
            vals = {"client_key": ck, "language": d.language,
                        "created_date_key": _date_key(created) if created else None,
                        "is_demo": bool(d.is_demo)}
            mk = c.execute(select(dw.dim_mission.c.mission_key).where(
                dw.dim_mission.c.dossier_id == d.id)).scalar()
            if mk is None:
                c.execute(insert(dw.dim_mission).values(
                    dossier_id=d.id, mission_name="", **vals))
                mk = c.execute(select(dw.dim_mission.c.mission_key).where(
                    dw.dim_mission.c.dossier_id == d.id)).scalar()
                self.counts["dim_mission"] += 1
            c.execute(update(dw.dim_mission).where(dw.dim_mission.c.mission_key == mk).values(
                mission_name=f"Mission {mk:03d}" if self.pseudo else d.name[:200], **vals))
            self.mission_keys[d.id] = mk
        self.user_keys: dict[str, int] = {r.user_id: r.user_key
                                          for r in c.execute(select(dw.dim_user))}
        for u in users:
            demo = bool(involved.get(u.id)) and all(involved[u.id])
            self.ensure_user(c, u.id, u.role, u.display_name, demo)
        # documents
        chunks = dict(o.execute(select(op.chunks.c.document_id, func.count())
                                .group_by(op.chunks.c.document_id)).all())
        alerts = dict(o.execute(
            select(op.chunks.c.document_id, func.count())
            .select_from(op.injection_alerts.join(op.chunks, op.chunks.c.id
                                                  == op.injection_alerts.c.chunk_id))
            .group_by(op.chunks.c.document_id)).all())
        self.doc_keys: dict[str, int] = {r.document_id: r.document_key
                                         for r in c.execute(select(dw.dim_document))}
        for d in o.execute(select(op.documents)):
            vals = {"mission_key": self.mission_keys[d.dossier_id], "mime": d.mime[:80],
                        "pages": d.pages, "chunk_count": chunks.get(d.id, 0),
                        "injection_alert_count": alerts.get(d.id, 0),
                        "is_demo": bool(self.dossiers[d.dossier_id].is_demo)}
            if d.id in self.doc_keys:
                c.execute(update(dw.dim_document).where(
                    dw.dim_document.c.document_id == d.id).values(**vals))
            else:
                c.execute(insert(dw.dim_document).values(document_id=d.id, **vals))
                self.doc_keys[d.id] = c.execute(select(dw.dim_document.c.document_key).where(
                    dw.dim_document.c.document_id == d.id)).scalar()
                self.counts["dim_document"] += 1
        self.model_keys: dict[tuple, int] = {
            (r.provider, r.model_name, r.adapter, r.config_label, bool(r.is_demo)): r.model_key
            for r in c.execute(select(dw.dim_model))}

    def ensure_user(self, c, user_id: str, role: str, label: str, demo: bool) -> int:
        key = self.user_keys.get(user_id)
        if key is None:
            c.execute(insert(dw.dim_user).values(
                user_id=user_id, role=role, user_label="", is_demo=demo))
            key = c.execute(select(dw.dim_user.c.user_key).where(
                dw.dim_user.c.user_id == user_id)).scalar()
            self.user_keys[user_id] = key
            self.counts["dim_user"] += 1
        c.execute(update(dw.dim_user).where(dw.dim_user.c.user_key == key).values(
            role=role, is_demo=demo,
            user_label=f"Utilisateur {key:03d}" if self.pseudo else label[:80]))
        return key

    def type_key(self, code: str) -> int:
        return TYPES[code][0]

    def model(self, c, provider, name, adapter, config, demo: bool) -> int:
        # `config_label` fait un caractère : seules les lettres du banc y entrent
        config = config if config in BENCH_LABELS else None
        k = (provider or "", name or "", adapter or None, config, demo)
        if k not in self.model_keys:
            c.execute(insert(dw.dim_model).values(
                provider=k[0][:40], model_name=k[1][:120], adapter=k[2], config_label=k[3],
                is_demo=demo))
            self.counts["dim_model"] += 1
            q = [dw.dim_model.c.provider == k[0], dw.dim_model.c.model_name == k[1],
                 dw.dim_model.c.is_demo == demo,
                 dw.dim_model.c.adapter.is_(None) if k[2] is None
                 else dw.dim_model.c.adapter == k[2],
                 dw.dim_model.c.config_label.is_(None) if k[3] is None
                 else dw.dim_model.c.config_label == k[3]]
            self.model_keys[k] = c.execute(select(dw.dim_model.c.model_key).where(*q)).scalar()
        return self.model_keys[k]

    # --- faits : générations
    def generations(self, c, o) -> None:
        since = self._since(c, "generation_runs")
        stmt = select(op.generation_runs).where(op.generation_runs.c.kind.in_(["section", "findings"]))
        if since:
            stmt = stmt.where(op.generation_runs.c.started_at >= _bind_dt(self.ope, since))
        runs = list(o.execute(stmt.order_by(op.generation_runs.c.started_at,
                                            op.generation_runs.c.id)))
        self._bump("generation_runs", [r.started_at for r in runs])
        known = {r for (r,) in c.execute(select(dw.fact_section_generation.c.run_id))}
        runs = [r for r in runs if r.id not in known]
        if not runs:
            return
        run_ids = [r.id for r in runs]
        verif, hits = defaultdict(list), {}
        for b in _batches(run_ids):
            for v in o.execute(select(op.verification_results).where(
                    op.verification_results.c.run_id.in_(b))):
                verif[v.run_id].append(v)
            hits.update(dict(o.execute(
                select(op.retrieval_hits.c.run_id, func.count()).where(
                    op.retrieval_hits.c.run_id.in_(b)).group_by(op.retrieval_hits.c.run_id)).all()))
        deliv = {d.id: d for d in o.execute(select(op.deliverables))}
        versions = defaultdict(list)
        for v in o.execute(select(op.deliverable_versions.c.deliverable_id,
                                  op.deliverable_versions.c.version,
                                  op.deliverable_versions.c.content,
                                  op.deliverable_versions.c.origin,
                                  op.deliverable_versions.c.created_at)
                           .order_by(op.deliverable_versions.c.created_at)):
            versions[v.deliverable_id].append(v)
        self._bump("deliverable_versions",
                   [v.created_at for vs in versions.values() for v in vs])

        plan = []
        for r in runs:
            dos = self.dossiers[r.dossier_id]
            demo = bool(dos.is_demo)
            d = deliv.get(r.deliverable_id)
            type_code = d.type if d else ("findings" if r.kind == "findings" else "tor")
            template = d.template_id if d else f"{type_code}-adhoc"
            section_key, _ = self.section(c, template, r.section_key or "_all", type_code)
            user = d.author_id if d else dos.owner_id
            ukey = self.user_keys.get(user) or self.ensure_user(c, user, "inconnu", "inconnu", demo)
            started = _utc(r.started_at)
            vs = verif.get(r.id, [])
            sentences, cites = self._citations(o, r, vs, versions.get(r.deliverable_id, []))
            status_n = Counter(v.status for v in vs)
            plan.append((r, {
                "run_id": r.id, "date_key": _date_key(started),
                "mission_key": self.mission_keys[r.dossier_id],
                "model_key": self.model(c, r.provider, r.model, r.adapter, r.config_label, demo),
                "section_key": section_key, "user_key": ukey, "status": r.status,
                "sentences_total": len(vs), "sentences_verified": status_n["verified"],
                "sentences_warning": status_n["warning"], "sentences_failed": status_n["failed"],
                "citations_total": len(cites), "citations_valid": sum(1 for x in cites if x["is_valid"]),
                "numbers_cited": sum(v.numbers_cited for v in vs),
                "numbers_found": sum(v.numbers_found for v in vs),
                "passages_retrieved": hits.get(r.id, 0), "attempts": r.attempts or 1,
                "latency_ms": r.latency_ms, "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                "is_demo": demo}, cites, sentences))
        _insert(c, dw.fact_section_generation, [p[1] for p in plan])
        self.counts["fact_section_generation"] += len(plan)
        keys = {}
        for b in _batches([p[1]["run_id"] for p in plan]):
            keys.update(dict(c.execute(select(
                dw.fact_section_generation.c.run_id,
                dw.fact_section_generation.c.generation_key).where(
                dw.fact_section_generation.c.run_id.in_(b))).all()))
        cit_rows, call_rows = [], []
        for r, g, cites, _ in plan:
            for x in cites:
                cit_rows.append(dict(generation_key=keys[g["run_id"]], is_demo=g["is_demo"], **x))
            attempts = max(int(g["attempts"]), 1)
            for i in range(attempts):
                def part(v, i=i, attempts=attempts):
                    return None if v is None else v // attempts + (v % attempts if i == 0 else 0)
                call_rows.append({
                    "date_key": g["date_key"], "model_key": g["model_key"], "mission_key": g["mission_key"],
                    "call_kind": r.kind, "latency_ms": part(r.latency_ms), "tokens_in": part(r.tokens_in),
                    "tokens_out": part(r.tokens_out),
                    "success": (g["status"] == "ok" and i == attempts - 1), "is_demo": g["is_demo"]})
        _insert(c, dw.fact_citation_check, cit_rows)
        _insert(c, dw.fact_llm_call, call_rows)
        self.counts["fact_citation_check"] += len(cit_rows)
        self.counts["fact_llm_call"] += len(call_rows)

    def _citations(self, o, run, verif, versions) -> tuple[int, list[dict]]:
        """Paires (phrase, source citée) lues dans la 1ʳᵉ version générée après le run."""
        if not run.deliverable_id or not run.section_key or run.kind != "section":
            return 0, []
        started = _utc(run.started_at)
        gen = [v for v in versions if v.origin == "generated" and _utc(v.created_at) >= started]
        if not gen:
            return 0, []
        content = gen[0].content if isinstance(gen[0].content, dict) else json.loads(gen[0].content)
        section = next((s for s in content.get("sections", [])
                        if s.get("section_key") == run.section_key), None)
        if not section:
            return 0, []
        by_idx = {v.sentence_index: v for v in verif}
        sources = {sid for s in section["sentences"] for sid in s.get("source_ids", [])}
        chunk_doc = {}
        for b in _batches(sources):
            chunk_doc.update({r.id: (r.document_id, r.dossier_id) for r in o.execute(
                select(op.chunks.c.id, op.chunks.c.document_id, op.chunks.c.dossier_id).where(
                    op.chunks.c.id.in_(b)))})
        issue_key = {r.issue_code: r.issue_key for r in self._issue_rows}
        rows = []
        for i, s in enumerate(section["sentences"]):
            v = by_idx.get(i)
            codes = [x.get("code") for x in (v.issues if v else [])]
            for sid in s.get("source_ids", []):
                doc = chunk_doc.get(sid)
                ok_source = doc is not None and doc[1] == run.dossier_id
                if not ok_source:
                    code = "FOREIGN_SOURCE" if doc is not None else "UNKNOWN_SOURCE"
                else:
                    other = [x for x in codes if x not in SOURCE_ISSUES]
                    code = other[0] if other else "NONE"
                rows.append({
                    "document_key": self.doc_keys.get(doc[0]) if ok_source else None,
                    "issue_key": issue_key.get(code, 0), "sentence_index": i,
                    "is_valid": ok_source,
                    "support": round(float(v.support), 3) if v else 0.0})
        return len(section["sentences"]), rows

    # --- faits : relectures et issues
    def reviews(self, c, o) -> None:
        since = self._since(c, "state_transitions")
        allt = list(o.execute(select(op.state_transitions).order_by(
            op.state_transitions.c.at, op.state_transitions.c.id)))
        self._bump("state_transitions", [t.at for t in allt])
        deliv = {d.id: d for d in o.execute(select(op.deliverables))}
        known = {r for (r,) in c.execute(select(dw.fact_review.c.transition_id))}
        prev: dict[str, datetime] = {}
        submitted: dict[str, datetime] = {}
        rows, approvals = [], []
        for t in allt:
            d = deliv[t.deliverable_id]
            at = _utc(t.at)
            before = prev.get(d.id) or _utc(d.created_at)
            if t.to_state == "in_review" and d.id not in submitted:
                submitted[d.id] = at
            since_sub = _hours(at, submitted[d.id]) if d.id in submitted else 0.0
            prev[d.id] = at
            if t.id in known or (since and at < since):
                continue
            dos = self.dossiers[d.dossier_id]
            demo = bool(dos.is_demo)
            ukey = self.user_keys.get(t.user_id) or self.ensure_user(
                c, t.user_id, "inconnu", "inconnu", demo)
            rows.append({
                "transition_id": t.id, "deliverable_id": d.id, "date_key": _date_key(at),
                "mission_key": self.mission_keys[d.dossier_id], "type_key": TYPES[d.type][0],
                "user_key": ukey, "from_state_key": STATES[t.from_state][0],
                "to_state_key": STATES[t.to_state][0], "version": t.version,
                "hours_since_previous": _hours(at, before), "hours_since_submission": since_sub,
                "has_reason": bool(t.reason), "is_demo": demo})
            if t.to_state == "approved":
                approvals.append((t, d, demo))
        _insert(c, dw.fact_review, rows)
        self.counts["fact_review"] += len(rows)
        self._outcomes(c, o, approvals)

    def _outcomes(self, c, o, approvals) -> None:
        existing = {(r.deliverable_id, r.approved_version, r.section_key)
                    for r in c.execute(select(dw.fact_section_outcome))}
        rows = []
        for t, d, demo in approvals:
            versions = list(o.execute(select(op.deliverable_versions).where(
                op.deliverable_versions.c.deliverable_id == d.id).order_by(
                op.deliverable_versions.c.version)))
            final = next((v for v in versions if v.version == t.version), None)
            if final is None:
                continue
            runs = list(o.execute(select(op.generation_runs).where(
                op.generation_runs.c.deliverable_id == d.id).order_by(
                op.generation_runs.c.started_at)))
            at = _utc(t.at)
            for sec in final.content.get("sections", []):
                code = sec["section_key"]
                skey, baseline = self.section(c, d.template_id, code, d.type)
                if (d.id, t.version, skey) in existing:
                    continue
                gen = next((v for v in reversed(versions)
                            if v.origin == "generated" and v.version <= t.version and any(
                                s["section_key"] == code for s in v.content["sections"])), None)
                gsec = next((s for s in gen.content["sections"] if s["section_key"] == code),
                            None) if gen else None
                gw, fw = _words(gsec), _words(sec)
                ratio = round(1 - difflib.SequenceMatcher(None, gw, fw, autojunk=False).ratio(), 4)
                last = [r for r in runs if r.section_key == code and _utc(r.started_at) <= at]
                m = last[-1] if last else None
                refused = bool((gsec and gsec.get("status") == "insufficient_evidence")
                               or (m is not None and m.status == "refused"))
                rows.append({
                    "deliverable_id": d.id, "approved_version": t.version, "date_key": _date_key(at),
                    "mission_key": self.mission_keys[d.dossier_id], "section_key": skey,
                    "model_key": self.model(c, m.provider if m else "", m.model if m else "inconnu",
                                         m.adapter if m else None,
                                         m.config_label if m else None, demo),
                    "generated_words": len(gw), "final_words": len(fw), "edit_ratio": ratio,
                    "unchanged": ratio == 0, "was_refused": refused,
                    "minutes_saved_est": round(float(baseline) * (1 - ratio), 1), "is_demo": demo})
                existing.add((d.id, t.version, skey))
        _insert(c, dw.fact_section_outcome, rows)
        self.counts["fact_section_outcome"] += len(rows)

    # --- orchestration
    def run(self) -> dict[str, int]:
        create_dw(self.dwe)
        with self.dwe.begin() as c:
            c.execute(insert(dw.etl_log).values(started_at=self.now, status="running"))
            log_id = c.execute(select(func.max(dw.etl_log.c.id))).scalar()
        try:
            with self.ope.connect() as o, self.dwe.begin() as c:
                self.static_dims(c)
                self._issue_rows = list(c.execute(select(dw.dim_issue)))
                self.reference_dims(c, o)
                self.generations(c, o)
                self.reviews(c, o)
                self.counts.update(snapshot.refresh(self, c, o, self.as_of))
                for src, val in self.wm.items():
                    c.execute(dw.etl_watermark.delete().where(
                        dw.etl_watermark.c.source_table == src))
                    c.execute(insert(dw.etl_watermark).values(
                        source_table=src, last_value=val, updated_at=self.now))
        except Exception as exc:
            with self.dwe.begin() as c:
                c.execute(update(dw.etl_log).where(dw.etl_log.c.id == log_id).values(
                    ended_at=self.now, status="error", error=type(exc).__name__))
            raise
        counts = {k: v for k, v in self.counts.items() if v}
        with self.dwe.begin() as c:
            c.execute(update(dw.etl_log).where(dw.etl_log.c.id == log_id).values(
                ended_at=self.now, status="ok", rows_by_table=counts))
        log.info("etl", extra={"rows": sum(counts.values())})
        return dict(self.counts)


def run_etl(op_engine: Engine, dw_engine: Engine, *, full: bool = False,
            now: datetime | None = None, pseudonymize: bool | None = None) -> dict[str, int]:
    """Charge l'entrepôt ; renvoie le nombre de lignes insérées par table.

    `pseudonymize` : remplace noms de clients, de missions et d'utilisateurs par des pseudonymes
    (par défaut : `settings.dw_pseudonymize` s'il existe, sinon faux).
    """
    if pseudonymize is None:
        from ..config import get_settings
        pseudonymize = bool(getattr(get_settings(), "dw_pseudonymize", False))
    return _Loader(op_engine, dw_engine, full, now or datetime.now(UTC), pseudonymize, as_of=now).run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Charge l'entrepôt dw depuis la base opérationnelle")
    parser.add_argument("--full", action="store_true", help="ignorer les filigranes")
    args = parser.parse_args()
    from ..config import get_settings
    from ..storage.engine import make_engine
    from .views_sql import create_views

    engine = make_engine(get_settings().storage_url)
    print(json.dumps(run_etl(engine, engine, full=args.full)))
    create_views(engine)


if __name__ == "__main__":
    main()
