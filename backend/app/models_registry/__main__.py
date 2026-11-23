"""Ligne de commande : python -m app.models_registry list | test NOM | activate NOM | rollback

Les mêmes règles que l'interface : l'activation exige un test réussi et est journalisée dans l'audit.
Le nom du modèle est toujours un modèle DÉJÀ installé dans le moteur local (rien n'est téléchargé).
"""

from __future__ import annotations

import argparse
import json
import sys

from app.config import get_settings

from .errors import RegistryError
from .service import RegistryService

OPERATOR = "cli"


def _audit(settings, action: str, name: str, details: dict) -> None:
    """Journal d'audit de l'application (base configurée) ; sans base, la trace reste dans l'historique du registre."""
    try:
        from app.storage import build_repository

        build_repository(settings).audit(OPERATOR, action, "model", name, details)
    except Exception as exc:  # noqa: BLE001
        print(f"(audit non écrit : {exc})", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.models_registry", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="modèles installés et modèle actif")
    for cmd in ("test", "activate"):
        sub.add_parser(cmd).add_argument("model")
    sub.add_parser("rollback", help="revenir au modèle précédent")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    args = parser.parse_args(argv)

    settings = get_settings()
    try:
        service = RegistryService(settings)
        if args.cmd == "list":
            data = service.list()
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
                return 0
            print(f"Moteur : {'joignable' if data['engine']['reachable'] else 'INJOIGNABLE'}"
                  f" | actif : {data['active'] or '—'} | précédent : {data['previous'] or '—'}")
            for m in data["models"]:
                test = m["test"]
                mark = "ok" if test and test["passed"] else ("échec" if test else "non testé")
                print(f"{'*' if m['active'] else ' '} {m['name']:<28} contexte max {m['max_context']}"
                      f" | {m['quantization'] or '?'} | test : {mark}")
            return 0
        if args.cmd == "test":
            report = service.test(args.model)
            for c in report["checks"]:
                print(f"[{c['status']:<4}] {c['label']}: {c['detail']}")
            print("RÉUSSI" if report["passed"] else "ÉCHEC")
            return 0 if report["passed"] else 1
        if args.cmd == "activate":
            result = service.activate(args.model, by=OPERATOR)
            _audit(settings, "model.activate", args.model, {"previous": result["previous"]})
        else:
            result = service.rollback(by=OPERATOR)
            _audit(settings, "model.rollback", result["active"], {"previous": result["previous"]})
        print(f"Modèle actif : {result['active']} (précédent : {result['previous']})")
        return 0
    except RegistryError as exc:
        print(f"{exc.code} : {exc.message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
