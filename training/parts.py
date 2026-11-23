"""UN entraînement découpé en parties qui se suivent (Colab ou toute machine qui peut couper).

  preuve      partie 0 : 2 pas, sauvegarde, reprise, export, réponse d'Ollama. Obligatoire.
  partie K    avance jusqu'à la borne K (50, 100, 150, 200) puis s'arrête ; relancer reprend.
  etat        où on en est, sans rien calculer.
  exporter    GGUF Q4_K_M + Modelfile + SHA-256 de la meilleure sauvegarde (adaptateur fusionné).
  exporter-base  la base Qwen3-4B par la MÊME chaîne, pour comparer honnêtement.

`--store` est le stockage persistant (Google Drive). Deux emplacements de sauvegarde y alternent :
une coupure pendant l'écriture laisse toujours la précédente intacte, et on réécrit au lieu de
supprimer (la corbeille de Drive compte dans le quota).
Codes de sortie : 0 fait · 4 arrêt propre, relancer · 5 preuve/export raté · 6 données refusées ·
7 ordre ou réglages incorrects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
from dataclasses import replace
from pathlib import Path

from training import export_gguf, guards
from training.runlog import file_sha256, library_versions
from training.train_lora import (
    DATA_REFUSED,
    EXPORT_FAILED,
    OK,
    STOPPED,
    RunConfig,
    check_data_policy,
    load_profile,
    make_backend,
    read_jsonl,
    release,
    render_prompt,
    total_steps,
)

WRONG_ORDER = 7
OPEN_LICENCES = ("CC BY", "Décision 2011/833/UE", "Licence Ouverte")
SLOTS = ("sauvegarde-a", "sauvegarde-b")


class Refused(RuntimeError):
    def __init__(self, message: str, code: int = WRONG_ORDER):
        super().__init__(message)
        self.code = code


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def check_public(profile: dict, examples: list[dict]) -> None:
    """Colab est un cloud : uniquement du public sous licence ouverte."""
    problem = check_data_policy(profile, examples)
    if problem:
        raise Refused(problem, DATA_REFUSED)
    for i, ex in enumerate(examples):
        meta = ex["meta"]
        if meta.get("confidential") or not str(meta["licence"]).startswith(OPEN_LICENCES):
            raise Refused(f"exemple {i} : pas un document public sous licence ouverte", DATA_REFUSED)


def fingerprint(cfg: RunConfig) -> str:
    """Change si les réglages ou les données changent : les parties ne se suivraient plus."""
    profile = {k: v for k, v in cfg.profile.items() if k != "base_model"}  # chemin local variable
    parts = [json.dumps(profile, sort_keys=True), str(cfg.seed), file_sha256(cfg.train_path),
             file_sha256(cfg.val_path)]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


# --------------------------------------------------------------------------- stockage persistant
class Store:
    def __init__(self, root: Path):
        self.root = root

    def _valid(self, slot: str) -> dict | None:
        m = _read_json(self.root / slot / "manifest.json")
        if not m or not m.get("complete"):
            return None
        for name, sha in m["files"].items():
            f = self.root / slot / name
            if not f.is_file() or file_sha256(f) != sha:
                return None
        return m

    def latest(self) -> tuple[str, dict] | None:
        found = [(s, m) for s in SLOTS if (m := self._valid(s))]
        return max(found, key=lambda x: x[1]["serial"]) if found else None

    def save(self, local: Path, state: dict, mark: str) -> None:
        last = self.latest()
        slot = SLOTS[1] if last and last[0] == SLOTS[0] else SLOTS[0]
        dest = self.root / slot
        _write_json(dest / "manifest.json", {"complete": False})
        files = {}
        for f in sorted(p for p in local.rglob("*") if p.is_file()):
            name = f.relative_to(local).as_posix()
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            with f.open("rb") as src, (dest / name).open("wb") as out:
                shutil.copyfileobj(src, out)
                out.flush()
                os.fsync(out.fileno())
            files[name] = file_sha256(f)
        _write_json(dest / "manifest.json", {  # en dernier : c'est lui qui valide la sauvegarde
            "complete": True, "serial": last[1]["serial"] + 1 if last else 1,
            "fingerprint": mark, "state": state, "files": files})

    def restore(self, local: Path) -> dict | None:
        last = self.latest()
        if not last:
            return None
        slot, manifest = last
        shutil.rmtree(local, ignore_errors=True)
        for name in manifest["files"]:
            (local / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.root / slot / name, local / name)
        return manifest


def save(cfg: RunConfig, backend, store: Store, state: dict, mark: str) -> None:
    local = cfg.run_dir / "a-sauver"
    shutil.rmtree(local, ignore_errors=True)
    local.mkdir(parents=True)
    backend.save_checkpoint(local)
    store.save(local, state, mark)


def save_best(backend, store_root: Path, best: dict, mark: str, cfg: RunConfig) -> None:
    """Adaptateur seul de la meilleure erreur de validation (l'export prend celui-ci, pas le dernier)."""
    local = cfg.run_dir / "meilleur-a-sauver"
    shutil.rmtree(local, ignore_errors=True)
    (local / "adapter").mkdir(parents=True)
    backend.save_adapter(local / "adapter")
    Store(store_root / "meilleur").save(local, best, mark)


def _tensors(root: Path) -> dict[str, str]:
    return {f.name: file_sha256(f) for f in (root / "adapter").glob("*.safetensors")}


def _seed_step(cfg: RunConfig, backend, step: int) -> None:
    if not backend.simulated:  # dropout identique, que l'on ait été coupé ou non
        backend.torch.manual_seed(cfg.seed + step)


# --------------------------------------------------------------------------- partie 0
def check_parity(cfg: RunConfig, tag: str, example: dict) -> None:
    """L'invite d'entraînement doit être exactement celle que le modèle verra dans Ollama."""
    from transformers import AutoTokenizer

    system, user = (m["content"] for m in example["messages"][:2])
    body = {"model": tag, "stream": False, "think": False, "keep_alive": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    seen = export_gguf.post("/api/chat", {**body, "_debug_render_only": True})
    ours = render_prompt(system, user)
    if seen.get("_debug_info", {}).get("rendered_template") != ours:
        raise export_gguf.ExportError("l'invite d'entraînement diffère de celle d'Ollama")
    out = export_gguf.post("/api/chat", {
        **body, "format": "json",
        "options": {"num_ctx": 8192, "num_predict": 1024, "temperature": 0, "seed": 0}})
    tok = AutoTokenizer.from_pretrained(cfg.profile["base_model"])
    ids = tok(ours, add_special_tokens=False)["input_ids"]
    if out.get("prompt_eval_count") != len(ids):
        raise export_gguf.ExportError(
            f"jetons différents : {len(ids)} à l'entraînement, {out.get('prompt_eval_count')} dans Ollama")
    try:
        json.loads(out["message"]["content"])
    except ValueError as e:
        raise export_gguf.ExportError("le modèle exporté ne rend pas de JSON lisible") from e


def prove(cfg: RunConfig, store_root: Path) -> int:
    train, val = read_jsonl(cfg.train_path), read_jsonl(cfg.val_path)
    check_public(cfg.profile, train + val)
    mark = fingerprint(cfg)
    proof_file = store_root / "preuve.json"
    if (_read_json(proof_file) or {}).get("fingerprint") == mark:
        print("Partie 0 déjà réussie : passe à la partie suivante.")
        return OK
    cfg = replace(cfg, run_id=f"{cfg.run_id}-preuve")
    store = Store(cfg.run_dir / "stockage")
    shutil.rmtree(cfg.run_dir, ignore_errors=True)

    print("1/4 deux pas d'apprentissage", flush=True)
    backend = make_backend(cfg, train, val)
    steps = getattr(backend, "steps", total_steps(len(train), cfg.profile))
    t0 = backend.now()
    for i in range(2):
        _seed_step(cfg, backend, i)
        loss = backend.train_step(i)
        if guards.check_loss(loss, None):
            raise Refused(f"perte invalide au pas {i + 1} : la preuve échoue", EXPORT_FAILED)
    seconds = (backend.now() - t0) / 2
    save(cfg, backend, store, {"step": 2}, mark)
    release(backend)

    print("2/4 reprise depuis la sauvegarde", flush=True)
    restored = cfg.run_dir / "repris"
    store.restore(restored)
    backend = make_backend(cfg, train, val)
    backend.load_checkpoint(restored)
    again = cfg.run_dir / "resauve"
    again.mkdir(parents=True)
    backend.save_checkpoint(again)
    if _tensors(restored) != _tensors(again):
        raise Refused("la reprise ne rend pas les mêmes poids", EXPORT_FAILED)
    if guards.check_loss(backend.train_step(2), None):
        raise Refused("perte invalide après reprise", EXPORT_FAILED)
    release(backend)

    print("3/4 export vers Ollama", flush=True)
    tag = f"{cfg.ollama_tag}-preuve"
    try:
        export_gguf.export(restored / "adapter", cfg.run_dir / "export", cfg.base_tag, cfg.simulate,
                           None if cfg.simulate else Path(cfg.profile["base_model"]),
                           None if cfg.simulate else tag)
        print("4/4 même invite, mêmes jetons, réponse JSON", flush=True)
        if not cfg.simulate:
            check_parity(cfg, tag, min(val, key=lambda e: len(e["messages"][1]["content"])))
    except export_gguf.ExportError as e:
        raise Refused(f"export : {e}", EXPORT_FAILED) from e
    _write_json(proof_file, {"fingerprint": mark, "steps": steps, "seconds_per_step": seconds,
                             "versions": library_versions()})
    print(f"PARTIE 0 RÉUSSIE. {steps} pas au total, {seconds:.1f} s par pas, "
          f"environ {seconds * steps / 4 / 60:.0f} min par partie.")
    return OK


# --------------------------------------------------------------------------- parties 1 à N
def bounds(steps: int, n_parts: int) -> list[int]:
    return [math.ceil(steps * k / n_parts) for k in range(n_parts + 1)]


def _checked(cfg: RunConfig, store_root: Path) -> tuple[str, dict]:
    mark = fingerprint(cfg)
    proof = _read_json(store_root / "preuve.json")
    if not proof:
        raise Refused("la partie 0 n'a pas réussi : lance-la d'abord")
    if proof["fingerprint"] != mark:
        raise Refused("données ou réglages différents de la partie 0 : les parties ne se suivraient plus")
    last = Store(store_root).latest()
    if last and last[1]["fingerprint"] != mark:
        raise Refused("la sauvegarde vient d'autres données ou réglages")
    return mark, proof


def train_part(cfg: RunConfig, store_root: Path, k: int, stop: guards.StopFlag | None = None) -> int:
    stop = stop or guards.StopFlag()
    p = cfg.profile
    if not 1 <= k <= p["parts"]:
        raise Refused(f"la partie doit être entre 1 et {p['parts']}")
    train, val = read_jsonl(cfg.train_path), read_jsonl(cfg.val_path)
    check_public(p, train + val)
    mark, proof = _checked(cfg, store_root)
    store = Store(store_root)
    limits = bounds(proof["steps"], p["parts"])
    start, end = limits[k - 1], limits[k]
    last = store.latest()
    state = last[1]["state"] if last else {"step": 0, "initial_loss": None, "evals": []}
    measured = {e["step"] for e in state["evals"]}
    if state.get("stopped_early"):
        print(f"Arrêt anticipé déjà décidé au pas {state['step']} (l'erreur de validation remontait) : "
              "passe à l'export, il prend la meilleure sauvegarde.")
        return OK
    if state["step"] >= end and end in measured:
        print(f"Partie {k} déjà faite (pas {state['step']}).")
        return OK
    if state["step"] < start or (start and start not in measured):
        raise Refused(f"termine d'abord la partie {k - 1} (on est au pas {state['step']})")

    backend = make_backend(cfg, train, val)
    if last:
        local = cfg.run_dir / "repris"
        store.restore(local)
        backend.load_checkpoint(local)
        print(f"Reprise au pas {state['step']}.", flush=True)
    else:
        state["evals"].append({"step": 0, "val_loss": backend.evaluate(0)})
        state["best"] = {"step": 0, "val_loss": state["evals"][0]["val_loss"]}
        state["bad_evals"] = 0
        save_best(backend, store_root, state["best"], mark, cfg)  # LoRA neuve = la base : repère de départ
        save(cfg, backend, store, state, mark)

    def measure(step: int) -> bool:
        """Mesure l'erreur de validation, garde le meilleur adaptateur ; vrai si elle remonte trop longtemps."""
        v = backend.evaluate(step)
        state["evals"].append({"step": step, "val_loss": v})
        best = state.setdefault("best", {"step": 0, "val_loss": state["evals"][0]["val_loss"]})
        if v < best["val_loss"]:
            state["best"], state["bad_evals"] = {"step": step, "val_loss": v}, 0
            save_best(backend, store_root, state["best"], mark, cfg)
            print(f"  validation {v:.4f} (meilleure jusqu'ici, pas {step})", flush=True)
            return False
        state["bad_evals"] = state.get("bad_evals", 0) + 1
        print(f"  validation {v:.4f} : au-dessus de la meilleure ({best['val_loss']:.4f}, pas {best['step']}) "
              f"[{state['bad_evals']}/{p.get('early_stop_patience', 2)}]", flush=True)
        return state["bad_evals"] >= p.get("early_stop_patience", 2)

    eval_every = p.get("eval_every")
    limits_g = guards.GuardConfig(cfg.min_free_gb, cfg.max_gpu_temp, 10.0)
    last_save = t_run = backend.now()
    while state["step"] < end:
        step = state["step"]
        _seed_step(cfg, backend, step)
        loss = backend.train_step(step)
        if guards.check_loss(loss, state["initial_loss"], limits_g.loss_explosion_factor):
            print(f"ARRÊT : perte invalide au pas {step + 1}. La sauvegarde précédente est intacte.")
            release(backend)
            return STOPPED  # ne jamais enregistrer des poids invalides
        state["step"] = step + 1
        if state["initial_loss"] is None:
            state["initial_loss"] = loss

        def free_fn(path: Path) -> float:
            fake = backend.free_gb(state["step"])
            return fake if fake is not None else guards.free_gb(path)

        def temp_fn() -> float | None:
            fake = backend.temperature(state["step"])
            return fake if fake is not None else (None if backend.simulated else guards.gpu_temperature())

        why = guards.check_all(loss, state["initial_loss"], cfg.run_dir.parent, limits_g,
                               free_fn=free_fn, temp_fn=temp_fn, stop=stop)
        early = step == start + 1  # preuve immédiate que la sauvegarde de cette partie marche
        if why or early or backend.now() - last_save >= cfg.save_every_min * 60:
            save(cfg, backend, store, state, mark)
            last_save = backend.now()
            print(f"  sauvegardé au pas {state['step']}", flush=True)
        if why:
            print(f"ARRÊT PROPRE : {why}. Relance la même cellule pour reprendre.")
            release(backend)
            return STOPPED
        if state["step"] % 5 == 0:
            state.setdefault("losses", []).append([state["step"], round(loss, 4)])
            print(f"[partie {k}] pas {state['step']}/{end}  perte {loss:.4f}", flush=True)
        if eval_every and state["step"] % eval_every == 0 and state["step"] < end and measure(state["step"]):
            state["stopped_early"] = True
            state["seconds"] = state.get("seconds", 0) + (backend.now() - t_run)
            save(cfg, backend, store, state, mark)
            release(backend)
            _write_json(store_root / f"bilan-partie-{k}.json", {"part": k, **state})
            print(f"ARRÊT ANTICIPÉ au pas {state['step']} : l'erreur de validation remonte. "
                  f"L'export prendra la meilleure sauvegarde (pas {state['best']['step']}).")
            return OK

    save(cfg, backend, store, state, mark)
    if measure(end):
        state["stopped_early"] = True
    state["seconds"] = state.get("seconds", 0) + (backend.now() - t_run)
    save(cfg, backend, store, state, mark)
    release(backend)
    _write_json(store_root / f"bilan-partie-{k}.json", {"part": k, **state})
    before, now = state["evals"][-2]["val_loss"], state["evals"][-1]["val_loss"]
    verdict = "il progresse" if now < before else "il ne progresse plus : montre ce résultat avant de continuer"
    print(f"PARTIE {k} TERMINÉE. Erreur de validation {before:.4f} -> {now:.4f} : {verdict}.")
    return OK


def status(cfg: RunConfig, store_root: Path) -> int:
    proof = _read_json(store_root / "preuve.json")
    print("Partie 0 :", "réussie" if proof else "à faire")
    if proof:
        last = Store(store_root).latest()
        state = last[1]["state"] if last else {"step": 0, "evals": []}
        print(f"Pas {state['step']}/{proof['steps']}")
        for k, end in enumerate(bounds(proof["steps"], cfg.profile["parts"])[1:], 1):
            found = [e for e in state["evals"] if e["step"] == end]
            text = f"faite, erreur {found[0]['val_loss']:.4f}" if found else "à faire"
            print(f"Partie {k} (jusqu'au pas {end}) : {text}")
    return OK


def summary(cfg: RunConfig, store_root: Path) -> int:
    """Dernière cellule : pas, pertes, durée, fichiers à télécharger."""
    proof = _read_json(store_root / "preuve.json")
    last = Store(store_root).latest()
    if not proof or not last:
        print("Rien à résumer : la partie 0 ou l'entraînement n'a pas eu lieu.")
        return OK
    state = last[1]["state"]
    best = state.get("best", {})
    print(f"Pas faits : {state['step']} sur {proof['steps']}"
          + ("  (ARRÊT ANTICIPÉ : l'erreur de validation remontait)" if state.get("stopped_early") else ""))
    print("Erreur de validation (pas -> perte) : "
          + ", ".join(f"{e['step']} -> {e['val_loss']:.3f}" for e in state["evals"]))
    if state.get("losses"):
        print("Perte d'entraînement (tous les 5 pas) : "
              + ", ".join(f"{s} -> {v:.3f}" for s, v in state["losses"]))
    if best:
        print(f"Meilleure erreur de validation : {best['val_loss']:.3f} au pas {best['step']} (c'est elle qui est exportée)")
        if best["step"] == 0:
            print("ATTENTION : aucun progrès sur la validation. Le modèle exporté vaut la base : n'en conclus rien.")
    print(f"Durée d'entraînement : {state.get('seconds', 0) / 60:.0f} min")
    for tag in ("cadrage-4b-lora", "cadrage-4b-base"):
        d = store_root / "modeles" / tag
        if (d / "model.gguf").is_file():
            sha = (d / "model.gguf.sha256").read_text("utf-8").split()[0]
            print(f"À télécharger : {d / 'model.gguf'}  ({(d / 'model.gguf').stat().st_size / 1e9:.2f} Go)  SHA-256 {sha}")
        else:
            print(f"Pas encore exporté : {tag}")
    print(f"Et le fichier {store_root / 'modeles' / 'SHA256SUMS.txt'}")
    return OK


def export_latest(cfg: RunConfig, store_root: Path, what: str = "lora") -> int:
    _checked(cfg, store_root)
    local = cfg.run_dir / "a-exporter"
    manifest = Store(store_root).restore(local)
    if not manifest or not manifest["state"]["step"]:
        raise Refused("rien à exporter : aucune partie entraînée")
    base_dir = None if cfg.simulate else Path(cfg.profile["base_model"])
    adapter, step = local / "adapter", manifest["state"]["step"]
    best = Store(store_root / "meilleur").restore(cfg.run_dir / "a-exporter-meilleur")
    if best:  # la meilleure erreur de validation, pas forcément la dernière sauvegarde
        adapter, step = cfg.run_dir / "a-exporter-meilleur" / "adapter", best["state"]["step"]
    jobs = {"lora": (adapter, "cadrage-4b-lora", f"LoRA au pas {step}"),
            "base": (None, "cadrage-4b-base", "base Qwen3-4B, même chaîne")}
    adapter_dir, tag, label = jobs[what]
    out = cfg.run_dir / f"export-{what}"
    try:
        export_gguf.export(adapter_dir, out, cfg.base_tag, cfg.simulate, base_dir,
                           None if cfg.simulate else tag)
    except export_gguf.ExportError as e:
        raise Refused(f"export : {e}", EXPORT_FAILED) from e
    dest = store_root / "modeles" / tag
    dest.mkdir(parents=True, exist_ok=True)
    for f in ("model.gguf", "Modelfile", "model.gguf.sha256"):
        shutil.copyfile(out / f, dest / f)
    sums = {t: (store_root / "modeles" / t / "model.gguf.sha256") for _, t, _ in jobs.values()}
    lines = [f"{p.read_text('utf-8').split()[0]}  {t}/model.gguf" for t, p in sorted(sums.items()) if p.is_file()]
    (store_root / "modeles" / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Exporté et testé ({label}) : {dest}")
    return OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("action", choices=["preuve", "partie", "etat", "exporter", "exporter-base", "resume"])
    ap.add_argument("k", type=int, nargs="?")
    ap.add_argument("--store", type=Path, required=True, help="stockage persistant (Drive)")
    ap.add_argument("--work", type=Path, default=Path("training/runs"))
    ap.add_argument("--data", type=Path, default=Path("training/data/real"))
    ap.add_argument("--profile", default="colab-parties")
    ap.add_argument("--base-dir", help="dossier local du modèle de base, à la révision épinglée")
    ap.add_argument("--simulate", action="store_true")
    a = ap.parse_args(argv)
    if a.action == "partie" and a.k is None:
        ap.error("numéro de partie manquant")
    p = load_profile(a.profile)
    if a.base_dir:
        p["base_model"] = a.base_dir
    elif not a.simulate and a.action not in ("etat", "resume"):
        ap.error("--base-dir est requis")
    cfg = RunConfig(profile=p, run_id=p["name"], runs_dir=a.work, train_path=a.data / "train.jsonl",
                    val_path=a.data / "val.jsonl", save_every_min=p["save_every_min"],
                    min_free_gb=p["min_free_gb"], max_gpu_temp=p["max_gpu_temp"], simulate=a.simulate,
                    base_tag=p.get("base_tag", "qwen3:4b"), ollama_tag="cadrage-4b-lora")
    stop = guards.StopFlag()
    stop.install()
    try:
        if a.action == "preuve":
            return prove(cfg, a.store)
        if a.action == "partie":
            return train_part(cfg, a.store, a.k, stop)
        if a.action == "etat":
            return status(cfg, a.store)
        if a.action == "resume":
            return summary(cfg, a.store)
        return export_latest(cfg, a.store, "base" if a.action == "exporter-base" else "lora")
    except Refused as e:
        print(f"REFUS : {e}")
        return e.code


if __name__ == "__main__":
    raise SystemExit(main())
