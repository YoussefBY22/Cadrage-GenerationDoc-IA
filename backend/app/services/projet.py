"""Fiche projet, recommandations des rapports d'audit et registre des entraînements.

Recommandations : extraction **par règles** sur les titres numérotés (« Recommandation n° 4 – … »,
« Recommendation 4: … »), sans calcul de modèle. Le consultant corrige le résultat (valider, fusionner,
ajouter, supprimer) et le contrôle de cohérence compare à ce que le rapport annonce. Jamais de 0
silencieux : un rapport sans titre numéroté est signalé « recommandations non détectées ».
Étape suivante, non faite : extraction par le modèle, en secours, pour les rapports sans numérotation.
"""

from __future__ import annotations

import base64
import io
import json
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import Engine, delete, insert, select, update

from ..domain.ids import new_id
from ..storage import schema as s

LOGO_MAX_OCTETS = 100_000  # après redimensionnement
LOGO_COTE = 256
RAPPORT = "diagnostic"  # rôle des documents traités comme rapports d'audit
ACTIFS = ("proposed", "validated")

# Titre numéroté : « Recommandation n° 1 – Titre », « Recommandation 2 : Titre », « Recommendation 3 - Title »
_TITRE = re.compile(
    r"\bRecomm(?:a|e)ndation\s+(?:n\s*[°o]\s*|no\.?\s*|#\s*)?(\d{1,2})\s*[–—:\-]\s*((?:(?!\bRecomm[ae]ndation\s).){3,300})", re.DOTALL)
# Numéros cités ailleurs : « recommandation n° 3 », « recommandations 1 à 4 ». Pas de trait d'union pour une
# plage : « Conclusions et recommandations 85 - 91 » (sommaire) désigne des points, pas des recommandations.
_CITE = re.compile(r"\b[Rr]ecomm(?:a|e)ndations?\s+(?:n\s*[°o]s?\s*|nos?\.?\s*)?(\d{1,2})\b"
                   r"(?:\s*(?:à|to|et|and)\s*(\d{1,2})\b)?(?!\s*[-–])")
MAX_NUMERO = 30
_FIN_TITRE = re.compile(r"(?<=\S)\s+(?=(?:La|Le|Les|L'|Nous|Il|Elle|The|We|It)\s)|[.;](?:\s|$)")


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ fiche projet
def _iso(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    return date.fromisoformat(v).isoformat()


def get_profile(engine: Engine, dossier_id: str) -> dict:
    with engine.connect() as c:
        d = c.execute(select(s.dossiers).where(s.dossiers.c.id == dossier_id)).first()
        p = c.execute(select(s.dossier_profiles).where(s.dossier_profiles.c.dossier_id == dossier_id)).first()
        docs = c.execute(select(s.documents.c.role).where(s.documents.c.dossier_id == dossier_id)).all()
    return {
        "dossier_id": dossier_id, "name": d.name, "client_name": d.client_name,
        "client_request": p.client_request if p else "", "request_summary": p.request_summary if p else "",
        "start_date": p.start_date if p else None, "end_date": p.end_date if p else None,
        "logo": p.logo if p else None, "documents": len(docs),
        "audit_reports": sum(1 for (r,) in docs if r == RAPPORT),
        "updated_at": p.updated_at.isoformat() if p and p.updated_at else None,
    }


def save_profile(engine: Engine, dossier_id: str, user_id: str, *, client_name: str | None = None,
                 client_request: str | None = None, request_summary: str | None = None,
                 start_date: str | None = None, end_date: str | None = None, logo: str | None = None,
                 clear_logo: bool = False, fields: set[str]) -> dict:
    """Met à jour les champs fournis (`fields`) ; résumé ≤ 200 caractères, dates ISO, fin ≥ début."""
    with engine.begin() as c:
        p = c.execute(select(s.dossier_profiles).where(s.dossier_profiles.c.dossier_id == dossier_id)).first()
        valeurs = dict(p._mapping) if p else {"dossier_id": dossier_id, "client_request": "", "request_summary": "",
                                               "start_date": None, "end_date": None, "logo": None}
        if "client_request" in fields:
            valeurs["client_request"] = (client_request or "").strip()
        if "request_summary" in fields:
            valeurs["request_summary"] = (request_summary or "").strip()[:200]
        if "start_date" in fields:
            valeurs["start_date"] = _iso(start_date)
        if "end_date" in fields:
            valeurs["end_date"] = _iso(end_date)
        if logo is not None:
            valeurs["logo"] = logo
        if clear_logo:
            valeurs["logo"] = None
        if valeurs["start_date"] and valeurs["end_date"] and valeurs["end_date"] < valeurs["start_date"]:
            raise ValueError("La date de fin précède la date de début")
        if not valeurs["request_summary"] and valeurs["client_request"]:
            valeurs["request_summary"] = _resume(valeurs["client_request"])
        valeurs.update(updated_by=user_id, updated_at=_now())
        if p:
            c.execute(update(s.dossier_profiles).where(s.dossier_profiles.c.dossier_id == dossier_id).values(**valeurs))
        else:
            c.execute(insert(s.dossier_profiles).values(**valeurs))
        if client_name and "client_name" in fields:
            c.execute(update(s.dossiers).where(s.dossiers.c.id == dossier_id).values(client_name=client_name.strip()))
    return get_profile(engine, dossier_id)


def _resume(texte: str, n: int = 200) -> str:
    """Première phrase de la demande, coupée à 200 caractères au mot près."""
    texte = " ".join(texte.split())
    phrase = re.split(r"(?<=[.!?])\s", texte, maxsplit=1)[0]
    if len(phrase) <= n:
        return phrase
    return phrase[: n - 1].rsplit(" ", 1)[0] + "…"


def logo_data_uri(contenu: bytes) -> str:
    """Image → PNG carré ≤ 256 px, en data URI ; refuse ce qui n'est pas une image ou reste trop lourd."""
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(contenu))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Le logo doit être une image PNG ou JPEG") from exc
    if img.format not in ("PNG", "JPEG", "WEBP", "GIF"):
        raise ValueError("Le logo doit être une image PNG ou JPEG")
    img = img.convert("RGBA")
    img.thumbnail((LOGO_COTE, LOGO_COTE))
    for cote in (LOGO_COTE, 192, 128, 96):
        if max(img.size) > cote:
            img.thumbnail((cote, cote))
        tampon = io.BytesIO()
        img.save(tampon, "PNG", optimize=True)
        if tampon.tell() <= LOGO_MAX_OCTETS:
            return "data:image/png;base64," + base64.b64encode(tampon.getvalue()).decode("ascii")
    raise ValueError("Le logo reste trop lourd après redimensionnement (100 Ko au plus)")


# ------------------------------------------------------------------ recommandations
def _titre(brut: str) -> str:
    brut = " ".join(brut.split())
    m = _FIN_TITRE.search(brut, 20)
    titre = brut[: m.start()] if m else brut
    return titre[:160].rstrip(" ,–—-")


def detecter(textes: list[tuple[str, int | None, str]]) -> tuple[list[dict], list[int]]:
    """[(chunk_id, page, texte)] → (titres numérotés, premier de chaque n°), numéros cités dans le texte."""
    titres: dict[int, dict] = {}
    cites: set[int] = set()
    for chunk_id, page, texte in textes:
        for m in _TITRE.finditer(texte):
            n = int(m.group(1))
            if 1 <= n <= MAX_NUMERO and n not in titres:
                titres[n] = {"number": n, "page": page, "title": _titre(m.group(2)), "chunk_id": chunk_id}
        for m in _CITE.finditer(texte):
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else a
            if 1 <= a <= b <= MAX_NUMERO:
                cites.update(range(a, b + 1))
    cites.update(titres)
    return sorted(titres.values(), key=lambda t: t["number"]), sorted(cites)


def extract(engine: Engine, dossier_id: str, user_id: str) -> dict:
    """(Re)lit chaque rapport d'audit du dossier. Ne touche pas aux lignes déjà corrigées par le consultant."""
    with engine.begin() as c:
        docs = c.execute(select(s.documents.c.id).where(
            s.documents.c.dossier_id == dossier_id, s.documents.c.role == RAPPORT)).scalars().all()
        for doc_id in docs:
            textes = [(r.id, r.page_start, r.text) for r in c.execute(
                select(s.chunks.c.id, s.chunks.c.page_start, s.chunks.c.text)
                .where(s.chunks.c.document_id == doc_id).order_by(s.chunks.c.ordinal))]
            titres, cites = detecter(textes)
            existants = c.execute(select(s.audit_recommendations).where(
                s.audit_recommendations.c.document_id == doc_id)).all()
            # Les propositions non revues sont remplacées ; validées, fusionnées, supprimées et ajouts restent.
            c.execute(delete(s.audit_recommendations).where(
                s.audit_recommendations.c.document_id == doc_id,
                s.audit_recommendations.c.origin == "rules", s.audit_recommendations.c.status == "proposed"))
            gardes = {r.number for r in existants if not (r.origin == "rules" and r.status == "proposed")}
            for t in titres:
                if t["number"] in gardes:
                    continue
                c.execute(insert(s.audit_recommendations).values(
                    id=new_id("rec"), dossier_id=dossier_id, document_id=doc_id, status="proposed",
                    origin="rules", updated_by=user_id, **t))
            ligne = {"numbers_seen": cites, "checked_at": _now()}
            if c.execute(select(s.report_checks.c.document_id).where(s.report_checks.c.document_id == doc_id)).first():
                c.execute(update(s.report_checks).where(s.report_checks.c.document_id == doc_id).values(**ligne))
            else:
                c.execute(insert(s.report_checks).values(document_id=doc_id, dossier_id=dossier_id, **ligne))
    return overview(engine, dossier_id)


def _vue(r) -> dict:
    return {"id": r.id, "document_id": r.document_id, "number": r.number, "page": r.page, "title": r.title,
            "status": r.status, "origin": r.origin, "merged_into": r.merged_into}


def controle(numeros_vus: list[int], actives: list[dict], extrait: bool, sans_reco: bool,
             traites: list[int] | tuple = ()) -> dict:
    """Écart entre ce que le rapport annonce et ce qui est retenu. `status` : ok | ecart | non_detectees.
    `traites` : numéros fusionnés ou supprimés par le consultant ; c'est un choix, pas un manque."""
    nums = [r["number"] for r in actives if r["number"] is not None]
    compte = Counter(nums)
    attendu = max(numeros_vus + nums, default=0)
    manquants = [n for n in range(1, attendu + 1) if n not in compte and n not in set(traites)]
    doublons = sorted(n for n, k in compte.items() if k > 1)
    if not actives and not numeros_vus:
        statut = "ok" if sans_reco else ("non_detectees" if extrait else "non_lu")
    elif manquants or doublons:
        statut = "ecart"
    else:
        statut = "ok"
    return {"status": statut, "expected": attendu or None, "extracted": len(actives),
            "missing": manquants, "duplicates": doublons}


def overview(engine: Engine, dossier_id: str) -> dict:
    """Recommandations par rapport, avec le contrôle de cohérence de chacun."""
    with engine.connect() as c:
        docs = c.execute(select(s.documents.c.id, s.documents.c.filename, s.documents.c.pages).where(
            s.documents.c.dossier_id == dossier_id, s.documents.c.role == RAPPORT)
            .order_by(s.documents.c.created_at, s.documents.c.id)).all()
        recs = c.execute(select(s.audit_recommendations).where(
            s.audit_recommendations.c.dossier_id == dossier_id)
            .order_by(s.audit_recommendations.c.number, s.audit_recommendations.c.created_at)).all()
        checks = {r.document_id: r for r in c.execute(select(s.report_checks).where(
            s.report_checks.c.dossier_id == dossier_id))}
    rapports = []
    for d in docs:
        toutes = [_vue(r) for r in recs if r.document_id == d.id]
        actives = [r for r in toutes if r["status"] in ACTIFS]
        ch = checks.get(d.id)
        traites = [r["number"] for r in toutes
                   if r["status"] in ("merged", "deleted") and r["number"] is not None]
        ctl = controle(list(ch.numbers_seen) if ch else [], actives, ch is not None,
                       bool(ch and ch.no_recommendation), traites)
        rapports.append({"document_id": d.id, "filename": d.filename, "pages": d.pages,
                         "recommendations": toutes, "check": ctl})
    alertes = sum(1 for r in rapports if r["check"]["status"] in ("ecart", "non_detectees"))
    return {"reports": rapports, "alerts": alertes,
            "validated": sum(1 for r in recs if r.status == "validated"),
            "active": sum(1 for r in recs if r.status in ACTIFS)}


def get_recommendation(engine: Engine, rec_id: str):
    with engine.connect() as c:
        return c.execute(select(s.audit_recommendations).where(s.audit_recommendations.c.id == rec_id)).first()


def add_recommendation(engine: Engine, dossier_id: str, user_id: str, *, document_id: str, title: str,
                       number: int | None, page: int | None) -> dict:
    with engine.begin() as c:
        doc = c.execute(select(s.documents.c.id).where(
            s.documents.c.id == document_id, s.documents.c.dossier_id == dossier_id)).first()
        if doc is None:
            raise LookupError("Rapport introuvable")
        rid = new_id("rec")
        c.execute(insert(s.audit_recommendations).values(
            id=rid, dossier_id=dossier_id, document_id=document_id, number=number, page=page,
            title=title.strip(), status="validated", origin="consultant", updated_by=user_id))
    return _vue(get_recommendation(engine, rid))


def patch_recommendation(engine: Engine, rec, user_id: str, *, fields: dict) -> dict:
    """Champs : title, number, page, status (validated | proposed | deleted), merge_into (id d'une autre)."""
    valeurs: dict = {k: v for k, v in fields.items() if k in ("title", "number", "page")}
    if "status" in fields:
        if fields["status"] not in ("validated", "proposed", "deleted"):
            raise ValueError("Statut inconnu")
        valeurs["status"] = fields["status"]
        valeurs["merged_into"] = None
    cible = fields.get("merge_into")
    if cible:
        autre = get_recommendation(engine, cible)
        if autre is None or autre.document_id != rec.document_id or autre.id == rec.id:
            raise ValueError("Fusion possible seulement avec une autre recommandation du même rapport")
        if autre.status not in ACTIFS:
            raise ValueError("La recommandation cible n'est plus active")
        valeurs.update(status="merged", merged_into=autre.id)
    valeurs.update(updated_by=user_id, updated_at=_now())
    with engine.begin() as c:
        c.execute(update(s.audit_recommendations).where(s.audit_recommendations.c.id == rec.id).values(**valeurs))
    return _vue(get_recommendation(engine, rec.id))


def confirm_no_recommendation(engine: Engine, dossier_id: str, document_id: str, value: bool) -> None:
    """Le consultant confirme qu'un rapport ne contient aucune recommandation : l'alerte tombe."""
    with engine.begin() as c:
        if c.execute(select(s.report_checks.c.document_id).where(s.report_checks.c.document_id == document_id)).first():
            c.execute(update(s.report_checks).where(s.report_checks.c.document_id == document_id)
                      .values(no_recommendation=value))
        else:
            c.execute(insert(s.report_checks).values(document_id=document_id, dossier_id=dossier_id,
                                                     numbers_seen=[], no_recommendation=value))


# ------------------------------------------------------------------ registre des entraînements
_CHAMPS_RUN = ("label", "run_date", "platform", "gpu", "examples", "test_examples", "duration_min",
               "steps_planned", "stop_step", "adopted", "outcome")


def import_training(engine: Engine, donnees: dict) -> str:
    """Un fichier JSON par entraînement (training/registre/*.json). Réimporter remplace l'entrée."""
    rid = str(donnees["id"])
    run = {k: donnees.get(k) for k in _CHAMPS_RUN}
    date.fromisoformat(run["run_date"])
    run["adopted"] = bool(run["adopted"])
    run["outcome"] = (run["outcome"] or "")[:200]
    points = [(int(p["step"]), float(p["val_loss"])) for p in donnees.get("validation", [])]
    if points:
        meilleur = min(points, key=lambda p: (p[1], p[0]))
        run.update(best_step=meilleur[0], best_val_loss=meilleur[1])
    else:  # pas de courbe publiée : on garde la dernière valeur connue, sans pas inventé
        run.update(best_step=donnees.get("best_step"), best_val_loss=donnees.get("best_val_loss"))
    scores = donnees.get("tests", [])
    with engine.begin() as c:
        for t in (s.training_task_scores, s.training_eval_points):
            c.execute(delete(t).where(t.c.run_id == rid))
        c.execute(delete(s.training_runs).where(s.training_runs.c.id == rid))
        c.execute(insert(s.training_runs).values(id=rid, **run))
        if points:
            c.execute(insert(s.training_eval_points), [{"run_id": rid, "step": a, "val_loss": b} for a, b in points])
        for sc in scores:
            if not 0 <= int(sc["correct"]) <= int(sc["total"]):
                raise ValueError(f"score incohérent : {sc}")
        if scores:
            c.execute(insert(s.training_task_scores), [
                {"run_id": rid, "model": sc["model"], "task": sc["task"], "correct": int(sc["correct"]),
                 "total": int(sc["total"])} for sc in scores])
    return rid


def list_trainings(engine: Engine) -> list[dict]:
    with engine.connect() as c:
        runs = c.execute(select(s.training_runs).order_by(s.training_runs.c.run_date)).all()
        points = c.execute(select(s.training_eval_points).order_by(s.training_eval_points.c.step)).all()
        scores = c.execute(select(s.training_task_scores)).all()
    out = []
    for r in runs:
        d = {k: getattr(r, k) for k in ("id", "best_step", "best_val_loss", *_CHAMPS_RUN)}
        d["validation"] = [{"step": p.step, "val_loss": p.val_loss} for p in points if p.run_id == r.id]
        d["tests"] = [{"model": x.model, "task": x.task, "correct": x.correct, "total": x.total}
                      for x in scores if x.run_id == r.id]
        out.append(d)
    return out


def main() -> None:
    import argparse

    from ..config import get_settings
    from ..storage.engine import make_engine

    parser = argparse.ArgumentParser(description="Registre des entraînements")
    parser.add_argument("action", choices=["import", "list"])
    parser.add_argument("fichiers", nargs="*", help="fichiers JSON (un par entraînement)")
    args = parser.parse_args()
    engine = make_engine(get_settings().storage_url)
    s.metadata.create_all(engine, tables=[s.training_runs, s.training_eval_points, s.training_task_scores])
    if args.action == "import":
        for f in args.fichiers:
            print("importé :", import_training(engine, json.loads(Path(f).read_text(encoding="utf-8"))))
    else:
        for r in list_trainings(engine):
            print(r["id"], r["run_date"], r["platform"], r["examples"], "ex.", "adopté" if r["adopted"] else "")


if __name__ == "__main__":
    main()
