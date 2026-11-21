"""Crée un compte (aucune route d'inscription n'existe) : à lancer depuis `backend/`.

    python scripts/create_user.py consultant@exemple.fr "Nom Affiché" consultant
    (le mot de passe est lu dans la variable CADRAGE_PASSWORD, sinon demandé au clavier)
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    from app.auth.passwords import hash_password
    from app.config import get_settings
    from app.storage import build_repository

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("email")
    ap.add_argument("display_name")
    ap.add_argument("role", choices=["consultant", "reviewer", "admin"])
    args = ap.parse_args(argv)
    password = os.environ.get("CADRAGE_PASSWORD") or getpass.getpass("Mot de passe : ")
    if len(password) < 12:
        print("Mot de passe trop court (12 caractères minimum).", file=sys.stderr)
        return 2
    repo = build_repository(get_settings())
    if repo.get_user_by_email(args.email):
        print("Ce compte existe déjà.", file=sys.stderr)
        return 1
    uid = repo.create_user(args.email, args.display_name, hash_password(password), args.role)
    print(uid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
