"""Situation courante pour les deux acteurs (07 §2.4) : livrables, sections, actions, prévisions.

Reconstruit entièrement à chaque ETL, donc idempotent. Aucun texte ne sort des tables
opérationnelles : des états, des compteurs, des dates et la **catégorie** du motif de renvoi.

Une phrase est **bloquante** si sa source n'existe pas dans le dossier, ou si le vérificateur l'a
rejetée à la génération et que son texte n'a pas changé depuis, tant qu'un responsable ne l'a pas
acquittée. Une citation sans source reste comptée, même acquittée (H7). Une phrase modifiée n'est pas
revérifiée ici : seule sa source est contrôlée.
"""

import json
from collections import defaultdict
from datetime import UTC, datetime
from itertools import product

from sqlalchemy import delete, insert, select

from ..storage import schema as op
from . import pilotage
from . import schema as dw


def _utc(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


def _day(d: datetime | None) -> int | None:
    return d.year * 10000 + d.month * 100 + d.day if d else None


def _hours(a: datetime, b: datetime) -> float:
    return round(max((a - b).total_seconds(), 0.0) / 3600.0, 2)


class _Snapshot:
    def __init__(self, loader, c, o):
        self.loader, self.c, self.o = loader, c, o
        self.deliverables = list(o.execute(select(op.deliverables).order_by(op.deliverables.c.id)))
        self.versions, self.transitions = defaultdict(list), defaultdict(list)
        self.runs, self.failed = defaultdict(list), defaultdict(set)
        for v in o.execute(select(op.deliverable_versions).order_by(op.deliverable_versions.c.version)):
            self.versions[v.deliverable_id].append(v)
        for t in o.execute(select(op.state_transitions).order_by(
                op.state_transitions.c.at, op.state_transitions.c.id)):
            self.transitions[t.deliverable_id].append(t)
        for r in o.execute(select(op.generation_runs).where(
                op.generation_runs.c.kind == "section").order_by(op.generation_runs.c.started_at)):
            self.runs[(r.deliverable_id, r.section_key)].append(r)
        v = op.verification_results.c
        for r in o.execute(select(v.run_id, v.sentence_index).where(v.status == "failed")):
            self.failed[r.run_id].add(r.sentence_index)
        self.chunk_dossier = dict(o.execute(select(op.chunks.c.id, op.chunks.c.dossier_id)).all())
        self.acked = defaultdict(set)
        a = op.audit_log.c
        for r in o.execute(select(a.object_id, a.details).where(a.action == "sentence.acknowledge")):
            x = r.details if isinstance(r.details, dict) else json.loads(r.details)
            self.acked[(r.object_id, x.get("version"))].add((x.get("section_key"), x.get("sentence_index")))
        m = op.dossier_members.c
        self.reviewer = {}
        for r in o.execute(select(m.dossier_id, m.user_id).where(m.role == "reviewer").order_by(m.user_id)):
            self.reviewer.setdefault(r.dossier_id, r.user_id)

    def as_of(self) -> datetime:
        """Maintenant, sauf jeu entièrement inventé : il est figé à son dernier événement."""
        if not self.deliverables or not all(
                self.loader.dossiers[d.dossier_id].is_demo for d in self.deliverables):
            return self.loader.now
        events = [_utc(t.at) for ts in self.transitions.values() for t in ts]
        events += [_utc(v.created_at) for vs in self.versions.values() for v in vs]
        return max(events) if events else self.loader.now

    @staticmethod
    def content(version) -> dict:
        return version.content if isinstance(version.content, dict) else json.loads(version.content)

    def measure(self, d, number: int | None, acknowledgements: bool = True) -> list[dict] | None:
        """Compteurs par section d'une version ; None si la version n'a pas de sections lisibles."""
        versions = self.versions[d.id]
        version = next((v for v in versions if v.version == number), None)
        if version is None:
            return None
        sections = self.content(version).get("sections")
        if not sections:
            return None
        out = []
        acked = self.acked[(d.id, number)] if acknowledgements else set()
        for sec in sections:
            key = sec.get("section_key")
            generated = next((v for v in reversed(versions)
                              if v.origin == "generated" and v.version <= number and any(
                                  s.get("section_key") == key
                                  for s in self.content(v).get("sections", []))), None)
            before: list[dict] = []
            failed: set[int] = set()
            if generated is not None:
                before = next(s.get("sentences", []) for s in self.content(generated)["sections"]
                              if s.get("section_key") == key)
                runs = [r for r in self.runs[(d.id, key)]
                        if _utc(r.started_at) <= _utc(generated.created_at)]
                failed = self.failed[runs[-1].id] if runs else set()
            row = {"code": key, "sentences": 0, "unchecked": 0, "blocking": 0, "citations": 0,
                   "invalid": 0, "refused": sec.get("status") == "insufficient_evidence"}
            for i, sentence in enumerate(sec.get("sentences", [])):
                same = i < len(before) and before[i].get("text") == sentence.get("text")
                sources = sentence.get("source_ids") or []
                bad = sum(1 for s in sources if self.chunk_dossier.get(s) != d.dossier_id)
                row["sentences"] += 1
                row["unchecked"] += not same
                row["citations"] += len(sources)
                row["invalid"] += bad
                row["blocking"] += bool((bad or (same and i in failed)) and (key, i) not in acked)
            out.append(row)
        return out

    def user_key(self, user_id: str | None, demo: bool) -> int | None:
        if not user_id:
            return None
        return self.loader.user_keys.get(user_id) or self.loader.ensure_user(
            self.c, user_id, "inconnu", "inconnu", demo)

    def deliverable(self, d, as_of: datetime) -> tuple[dict, list[dict]]:
        trans = self.transitions[d.id]
        dossier = self.loader.dossiers[d.dossier_id]
        demo = bool(dossier.is_demo)
        sent = [t for t in trans if t.to_state == "in_review"]
        decisions = [t for t in trans if t.to_state in ("approved", "rejected")]
        rejected = [t for t in trans if t.to_state == "rejected"]
        created = _utc(d.created_at)
        since = _utc(trans[-1].at) if trans else created
        touched = [since] + [_utc(v.created_at) for v in self.versions[d.id]]
        sections = self.measure(d, d.current_version)

        def total(key: str):
            return sum(int(s[key]) for s in sections) if sections is not None else None

        first_blocking = first_rejected = first_decided = None
        if sent:
            at_submission = self.measure(d, sent[0].version, acknowledgements=False)
            if at_submission is not None:
                first_blocking = sum(s["blocking"] for s in at_submission)
            first = next((t for t in decisions if _utc(t.at) >= _utc(sent[0].at)), None)
            if first:
                first_rejected, first_decided = first.to_state == "rejected", _utc(first.at)
        returned = bool(d.state in ("draft", "rejected") and rejected and
                        (not sent or _utc(rejected[-1].at) >= _utc(sent[-1].at)))
        reviewer = decisions[-1].user_id if decisions else self.reviewer.get(d.dossier_id)
        row = {
            "deliverable_id": d.id, "mission_key": self.loader.mission_keys[d.dossier_id],
            "client_key": self.loader.client_keys_by_dossier[d.dossier_id],
            "type_key": self.loader.type_key(d.type), "author_key": self.user_key(d.author_id, demo),
            "reviewer_key": self.user_key(reviewer, demo), "state": d.state,
            "created_date_key": _day(created),
            "submitted_date_key": _day(_utc(sent[0].at)) if sent else None,
            "approved_date_key": _day(since) if d.state == "approved" else None,
            "as_of": as_of.strftime("%Y-%m-%d %H:%M"), "state_age_hours": _hours(as_of, since),
            "idle_hours": _hours(as_of, max(touched)),
            "version": d.current_version, "submissions": len(sent), "rejections": len(rejected),
            "returned": returned,
            "reason_code": pilotage.reason_code(rejected[-1].reason) if returned else None,
            "sections": len(sections) if sections is not None else None,
            "refused_sections": total("refused"), "sentences": total("sentences"),
            "unchecked_sentences": total("unchecked"), "blocking_open": total("blocking"),
            "citations_total": total("citations"), "citations_invalid": total("invalid"),
            "delay_hours": _hours(since, _utc(sent[0].at)) if d.state == "approved" and sent else None,
            "first_blocking": first_blocking, "first_rejected": first_rejected,
            "risk": None, "risk_low": None, "risk_high": None, "risk_n": None, "is_demo": demo,
            "_submitted": [_utc(t.at) for t in sent], "_created": created,
            "_first_decided": first_decided,
        }
        detail = []
        for s in sections or []:
            key, _ = self.loader.section(self.c, d.template_id, s["code"], d.type)
            detail.append({
                "deliverable_id": d.id, "section_key": key, "sentences": s["sentences"],
                "blocking": s["blocking"], "citations_invalid": s["invalid"], "refused": s["refused"],
                "priority": pilotage.section_priority(s["blocking"], s["invalid"], s["refused"]),
                "is_demo": demo})
        return row, detail

    def forecasts(self, rows: list[dict], as_of: datetime) -> tuple[list[dict], list[dict], dict]:
        """Une prévision et sa série par périmètre, plus le modèle de risque.

        Périmètre : client et type, pour tout le cabinet, un consultant ou un responsable. Chaque
        rôle RLS lit ainsi sa propre prévision, jamais le total du cabinet.
        """
        real = [r for r in rows if not r["is_demo"]]
        base = real or rows                     # les données inventées ne nourrissent jamais le réel
        if not base:
            return [], [], pilotage.risk_model([])
        cases = [{"submitted": r["_submitted"][0], "decided": r["_first_decided"],
                  "blocking": r["first_blocking"] > 0, "rejected": r["first_rejected"]}
                 for r in base if r["first_rejected"] is not None and r["first_blocking"] is not None]
        risk = pilotage.risk_model(cases)
        start = min(r["_created"] for r in base)
        dims = [[None, *sorted({r[k] for r in base})] for k in ("client_key", "type_key")]
        people = [(None, None)]
        people += [(a, None) for a in sorted({r["author_key"] for r in base})]
        people += [(None, v) for v in sorted({r["reviewer_key"] for r in base if r["reviewer_key"]})]
        demo = all(r["is_demo"] for r in base)
        out, points = [], []
        for i, (client, kind, (author, reviewer)) in enumerate(product(*dims, people), 1):
            scope = [r for r in base if client in (None, r["client_key"])
                     and kind in (None, r["type_key"]) and author in (None, r["author_key"])
                     and reviewer in (None, r["reviewer_key"])]
            times = [t for r in scope for t in r["_submitted"]]
            counts = pilotage.weekly_counts(times, start, as_of)
            f = pilotage.forecast_load(counts)
            points += [{"forecast_key": i, "is_demo": demo, **p}
                       for p in pilotage.forecast_series(counts, as_of, f)]
            out.append({"forecast_key": i, "client_key": client, "type_key": kind, "author_key": author,
                        "reviewer_key": reviewer,
                        "as_of": as_of.strftime("%Y-%m-%d %H:%M"),
                        "queue": sum(r["state"] == "in_review" for r in scope),
                        **f, "risk_status": risk["status"], "risk_brier": risk["brier"],
                        "risk_brier_naive": risk["brier_naive"], "risk_tested": risk["tested"],
                        "is_demo": demo})
        return out, points, risk

    def run(self, as_of: datetime | None) -> dict[str, int]:
        as_of = as_of or self.as_of()
        rows, details = [], []
        for d in self.deliverables:
            row, detail = self.deliverable(d, as_of)
            rows.append(row)
            details += detail
        forecasts, points, risk = self.forecasts(rows, as_of)
        if risk["status"] == "ok":
            for r in rows:
                if r["state"] == "in_review" and r["blocking_open"] is not None:
                    g = risk["groups"][r["blocking_open"] > 0]
                    r.update(risk=g["rate"], risk_low=g["low"], risk_high=g["high"], risk_n=g["n"])
        actions = [{"deliverable_id": r["deliverable_id"], "rule_code": code, "is_demo": r["is_demo"]}
                   for r in rows for code in pilotage.actions_for(r)]
        clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
        counts = {}
        for table, data in ((dw.fact_action, actions), (dw.fact_section_current, details),
                            (dw.fact_forecast, forecasts), (dw.fact_forecast_point, points),
                            (dw.fact_deliverable, clean)):
            self.c.execute(delete(table))
            for i in range(0, len(data), 200):
                self.c.execute(insert(table), data[i:i + 200])
            counts[table.name] = len(data)
        return counts


def refresh(loader, c, o, as_of: datetime | None = None) -> dict[str, int]:
    return _Snapshot(loader, c, o).run(as_of)
