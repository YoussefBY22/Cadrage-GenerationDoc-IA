"""Rejoue le parcours complet du produit (démo du jury), de bout en bout, via l'API HTTP réelle.

    python scripts/demo_parcours.py            # lance un serveur local jetable (SQLite, modèle « demo »)
    python scripts/demo_parcours.py --url http://localhost:8000 --email … --password … \
        --reviewer-email … --reviewer-password …   # joue sur une instance existante (mode token)

Étapes : comptes → dossier → import du corpus synthétique → recherche → constats → validation →
feuille de route → ToR (sections vérifiées) → relecture → approbation → export DOCX et PPTX.
À lancer depuis `backend/`. Aucun accès réseau externe : seul le serveur local est contacté.
"""

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

PASSWORD = "demo-parcours-2026"


def step(n: int, title: str) -> None:
    print(f"\n[{n:02d}] {title}", flush=True)


def ok(resp: httpx.Response, expected: int | tuple[int, ...] = 200):
    codes = (expected,) if isinstance(expected, int) else expected
    if resp.status_code not in codes:
        raise SystemExit(
            f"ÉCHEC {resp.request.method} {resp.request.url.path} -> {resp.status_code} {resp.text[:300]}"
        )
    if resp.headers.get("content-type", "").startswith("application/json"):
        return resp.json()
    return resp.content


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def spawn_server(workdir: Path):
    """Serveur jetable : base SQLite et fichiers dans ``workdir``, modèle de démonstration."""
    env = {
        **os.environ,
        "LLM_PROVIDER": "demo",
        "AUTH_MODE": "token",
        "STORAGE_URL": f"sqlite+pysqlite:///{(workdir / 'app.db').as_posix()}",
        "UPLOAD_DIR": str(workdir / "uploads"),
        "DATABASE_URL": "",
    }
    os.environ.update(env)
    from app.auth.passwords import hash_password
    from app.config import get_settings
    from app.storage import build_repository

    get_settings.cache_clear()
    repo = build_repository(get_settings())
    repo.create_user("consultant@demo.local", "Consultante démo", hash_password(PASSWORD), "consultant")
    repo.create_user("relecteur@demo.local", "Relecteur démo", hash_password(PASSWORD), "reviewer")
    repo.engine.dispose()
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning"],
        cwd=BACKEND,
        env=env,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/health", timeout=1).status_code == 200:
                return proc, url
        except httpx.HTTPError:
            time.sleep(0.2)
    proc.terminate()
    raise SystemExit("Le serveur n'a pas démarré.")


def login(c: httpx.Client, email: str, password: str) -> dict:
    body = ok(c.post("/api/v1/auth/login", json={"email": email, "password": password}))
    return {"headers": {"Authorization": f"Bearer {body['token']}"}, "id": body["user"]["id"]}


def run(url: str, creds: dict, out_dir: Path) -> None:
    from app.generation.template_loader import load_template
    from eval.corpus.generate import generate

    t0 = time.perf_counter()
    with httpx.Client(base_url=url, timeout=120) as c:
        step(1, "Connexion du consultant et du relecteur")
        cons = login(c, creds["email"], creds["password"])
        rev = login(c, creds["reviewer_email"], creds["reviewer_password"])
        ch, rh = cons["headers"], rev["headers"]

        step(2, "Création du dossier et ajout du relecteur")
        gold = generate(7, out_dir / "corpus")
        inst = gold.documents[0].institution
        did = ok(c.post("/api/v1/dossiers", headers=ch, json={"name": inst, "client_name": inst}), 201)["id"]
        ok(c.post(f"/api/v1/dossiers/{did}/members", headers=ch,
                  json={"user_id": rev["id"], "role": "reviewer"}), 201)

        step(3, "Import des documents du corpus synthétique")
        for d in (d for d in gold.documents if d.institution == inst):
            path = out_dir / "corpus" / next(iter(d.paths.values()))
            ok(c.post(f"/api/v1/dossiers/{did}/documents", headers=ch,
                      files={"file": (path.name, path.read_bytes())}), 201)
            print(f"     {path.name}")

        step(4, "Recherche mixte")
        hits = ok(c.post(f"/api/v1/dossiers/{did}/search", headers=ch,
                         json={"texts": ["taux de pertes du réseau"], "k": 3}))
        print(f"     {len(hits)} passages ; premier : {hits[0]['chunk']['text'][:80]!r}")

        step(5, "Extraction et validation des constats")
        ext = ok(c.post(f"/api/v1/dossiers/{did}/findings:extract", headers=ch))
        for f in ext["findings"]:
            ok(c.patch(f"/api/v1/findings/{f['id']}", headers=ch, json={"validated": True}))
        print(f"     {len(ext['findings'])} constats validés")

        step(6, "Feuille de route priorisée")
        road = ok(c.post(f"/api/v1/dossiers/{did}/roadmap:generate", headers=ch, json={}))
        top = road["roadmap"]["items"][0]["initiative"]
        print(f"     initiative n°1 : {top['title']}")

        step(7, "Termes de référence : génération des sections avec vérification")
        tor = ok(c.post(f"/api/v1/dossiers/{did}/deliverables", headers=ch,
                        json={"type": "tor", "initiative_id": top["id"]}), 201)["deliverable_id"]
        # Budget, profils, calendrier : décisions humaines, jamais dans un diagnostic. Le consultant
        # les saisit puis les confirme (deux appels) ; sans elles, les sections sont refusées.
        texts = {"schedule": "Mission de douze semaines, du lancement à la remise du rapport final.",
                 "profile": "Un chef de projet senior justifiant de huit années d'expérience.",
                 "criterion": "Offres notées sur 100 : qualité technique 70, prix 30."}
        for spec in load_template("tor", "fr").sections:
            for cat in spec.requires_decisions:
                d = ok(c.post(f"/api/v1/dossiers/{did}/decisions", headers=ch,
                              json={"category": cat, "text": texts.get(cat, f"Décision {cat}.")}), 201)
                ok(c.post(f"/api/v1/decisions/{d['id']}:confirm", headers=ch))
                print(f"     décision confirmée : {cat}")
        for spec in load_template("tor", "fr").sections:
            r = ok(c.post(f"/api/v1/deliverables/{tor}/sections/{spec.key}:generate", headers=ch))
            print(f"     {spec.key:<24} TPV = {r['tpv']:.2f}")

        step(8, "Relecture puis approbation (deux personnes distinctes)")
        ok(c.post(f"/api/v1/deliverables/{tor}/transitions", headers=ch, json={"to": "in_review"}))
        ok(c.post(f"/api/v1/deliverables/{tor}/transitions", headers=rh, json={"to": "approved"}))

        step(9, "Export DOCX et PPTX")
        for fmt in ("docx", "pptx"):
            data = ok(c.post(f"/api/v1/deliverables/{tor}/exports", headers=rh, json={"format": fmt}))
            target = out_dir / f"tor.{fmt}"
            target.write_bytes(data)
            print(f"     {target} ({len(data) // 1024} Ko)")

        step(10, "Journal d'audit")
        audit = ok(c.get("/api/v1/audit", headers=rh))
        print(f"     {len(audit) if isinstance(audit, list) else audit} entrées")
    print(f"\nParcours terminé en {time.perf_counter() - t0:.1f} s.")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):  # console Windows (cp1252) : jamais d'exception d'encodage
        stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--url")
    ap.add_argument("--email")
    ap.add_argument("--password")
    ap.add_argument("--reviewer-email")
    ap.add_argument("--reviewer-password")
    ap.add_argument("--out", default=None, help="dossier de sortie (défaut : dossier temporaire)")
    args = ap.parse_args()
    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="demo_parcours_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = None
    try:
        if args.url:
            creds = {"email": args.email, "password": args.password,
                     "reviewer_email": args.reviewer_email, "reviewer_password": args.reviewer_password}
            if not all(creds.values()):
                raise SystemExit("Avec --url : --email --password --reviewer-email --reviewer-password.")
            url = args.url
        else:
            proc, url = spawn_server(out_dir)
            creds = {"email": "consultant@demo.local", "password": PASSWORD,
                     "reviewer_email": "relecteur@demo.local", "reviewer_password": PASSWORD}
        run(url, creds, out_dir)
    finally:
        if proc:
            proc.terminate()
            proc.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
