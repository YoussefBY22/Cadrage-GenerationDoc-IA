"""Entraînement QLoRA avec garde-fous (08 §7.3). Le mode --simulate n'importe ni torch ni peft.

Étapes : (1) mesure de 50 pas -> estimation -> refus si > --budget-hours ;
(2) essai sur 1 % + export test ; (3) long entraînement avec points de reprise, reprise automatique,
arrêts propres (perte invalide, disque, température, Ctrl+C) ; journal run.json tout du long.

Exemple (simulation, sans GPU) :
  python -m training.train_lora --simulate --train t.jsonl --val v.jsonl --run-id essai1
Codes de sortie : 0 terminé · 3 budget dépassé · 4 arrêt propre (reprise possible) · 5 export
raté · 6 données refusées.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from training import export_gguf, guards
from training.runlog import RunLog

OK, REFUSED_BUDGET, STOPPED, EXPORT_FAILED, DATA_REFUSED = 0, 3, 4, 5, 6
PROFILES_DIR = Path(__file__).parent / "profiles"
MEASURE_STEPS = 50  # surchargeable par le profil (measure_steps)


class SimulatedKill(BaseException):
    """Coupure brutale simulée (pas de sauvegarde propre) : teste la reprise."""


# --------------------------------------------------------------------------- configuration
@dataclass
class RunConfig:
    profile: dict
    run_id: str
    runs_dir: Path
    train_path: Path
    val_path: Path | None
    seed: int = 7
    budget_hours: float = 8.0
    save_every_min: float = 20.0
    min_free_gb: float = 5.0
    max_gpu_temp: float = 83.0
    simulate: bool = False
    base_tag: str = "qwen3:1.7b"
    ollama_tag: str = "cadrage-lora"
    stop_after_trial: bool = False
    sim: dict = field(default_factory=dict)

    @property
    def run_dir(self) -> Path:
        return self.runs_dir / self.run_id


def load_profile(name_or_path: str) -> dict:
    p = Path(name_or_path)
    if not p.is_file():
        p = PROFILES_DIR / f"{name_or_path}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def check_data_policy(profile: dict, examples: list[dict]) -> str | None:
    """Licence obligatoire ; profil « public_data_only » (Colab) : aucune donnée confidentielle."""
    for i, ex in enumerate(examples):
        meta = ex.get("meta") or {}
        if not str(meta.get("licence", "")).strip():
            return f"exemple {i} sans licence dans meta"
        if profile.get("public_data_only") and meta.get("confidential"):
            return f"exemple {i} confidentiel : interdit avec le profil {profile.get('name')}"
    return None


def render_prompt(system: str, user: str) -> str:
    """Invite identique, caractère pour caractère, à celle d'Ollama (qwen3:1.7b, think: false).

    Le gabarit Hugging Face diffère : ni « /no_think », ni double saut de ligne après « system ».
    L'égalité est revérifiée contre Ollama à la partie 0 (training/parts.py).
    """
    return (f"<|im_start|>system\n\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user} /no_think<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n\n</think>\n\n")


def total_steps(n_examples: int, profile: dict) -> int:
    n_examples = min(n_examples, profile.get("max_train_examples") or n_examples)
    per_step = profile["batch_size"] * profile["grad_accum"]
    return max(1, math.ceil(n_examples * profile["epochs"] / per_step))


# --------------------------------------------------------------------------- moteurs
class SimBackend:
    """Boucle factice : pas de modèle, perte déterministe, horloge virtuelle, pannes injectables."""

    simulated = True

    def __init__(self, cfg: RunConfig):
        s = cfg.sim
        self.step_seconds = s.get("step_seconds", 30.0)
        self.nan_at, self.kill_at = s.get("nan_at"), s.get("kill_at")
        self.disk_full_at, self.hot_at = s.get("disk_full_at"), s.get("hot_at")
        self.plateau_at = s.get("plateau_at")
        self._clock = 0.0

    def now(self) -> float:
        return self._clock

    def train_step(self, step: int) -> float:
        self._clock += self.step_seconds
        if self.kill_at is not None and step + 1 == self.kill_at:
            raise SimulatedKill(f"coupure simulée au pas {step + 1}")
        if self.nan_at is not None and step + 1 >= self.nan_at:
            return float("nan")
        return 2.0 * math.exp(-step / 300) + 0.3 + 0.01 * math.sin(step)

    def evaluate(self, step: int) -> float:
        s = step if self.plateau_at is None else min(step, self.plateau_at)
        return 2.0 * math.exp(-s / 300) + 0.3 + (step - s) * 1e-4

    def free_gb(self, step: int) -> float | None:
        return 0.5 if self.disk_full_at is not None and step >= self.disk_full_at else None

    def temperature(self, step: int) -> float | None:
        return 95.0 if self.hot_at is not None and step >= self.hot_at else None

    def save_checkpoint(self, d: Path) -> None:
        (d / "sim_state.json").write_text('{"backend": "sim"}', encoding="utf-8")

    def load_checkpoint(self, d: Path) -> None:
        assert (d / "sim_state.json").is_file()

    def save_adapter(self, d: Path) -> None:
        d.mkdir(parents=True, exist_ok=True)
        (d / "adapter_config.json").write_text('{"simulated": true}', encoding="utf-8")


class TorchBackend:
    """Vrai QLoRA (torch, transformers, peft, bitsandbytes) : imports paresseux, JAMAIS exécuté
    pendant la nuit de développement (pas de GPU) ; à valider avec l'utilisateur (voir README)."""

    simulated = False

    def __init__(self, cfg: RunConfig, train: list[dict], val: list[dict]):
        import torch
        from peft import LoraConfig, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            get_cosine_schedule_with_warmup,
        )

        p = cfg.profile
        self.torch, self.p = torch, p
        torch.manual_seed(cfg.seed)
        self.tok = AutoTokenizer.from_pretrained(p["base_model"])
        # GTX 1650 (sans cœurs tenseurs) : les produits fp16 y sont ~4x plus lents que fp32 (mesuré en T5).
        self.fp16 = p.get("compute_dtype", "fp16") == "fp16"
        self.dtype = torch.float16 if self.fp16 else torch.float32
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                 bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=self.dtype)
        self.quantized = p.get("quant", "none") != "none" and _bnb_available()
        kw = {"quantization_config": bnb} if self.quantized else {}
        model = AutoModelForCausalLM.from_pretrained(
            p["base_model"], dtype=self.dtype, device_map={"": 0}, **kw)
        # prepare_model_for_kbit_training passerait les plongements (151 k x 2 048) en fp32 : trop pour 4 Go.
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        lc = p["lora"]
        self.model = get_peft_model(model, LoraConfig(
            r=lc["r"], lora_alpha=lc["alpha"], lora_dropout=lc["dropout"],
            target_modules=lc["modules"], task_type="CAUSAL_LM"))
        params = [x for x in self.model.parameters() if x.requires_grad]
        for x in params:  # adaptateur en fp32 (maître), le calcul reste en fp16 (autocast)
            x.data = x.data.float()
        if self.quantized:
            import bitsandbytes as bnb_lib

            self.opt = bnb_lib.optim.PagedAdamW8bit(params, lr=p["lr"])
        else:
            self.opt = torch.optim.AdamW(params, lr=p["lr"])
        import random

        train = random.Random(cfg.seed).sample(train, len(train))  # le plafond garde un mélange représentatif
        self.train = self._encode(train, p.get("max_train_examples"))
        self.steps = total_steps(len(self.train), p)
        self.sched = get_cosine_schedule_with_warmup(
            self.opt, max(1, int(p["warmup_ratio"] * self.steps)), self.steps)
        self.scaler = torch.amp.GradScaler("cuda", enabled=self.fp16)  # fp16 : pas de bf16 sur ces GPU
        self.val = self._encode(val, p.get("val_examples", 64))
        self.order = list(range(len(self.train)))
        import random

        random.Random(cfg.seed).shuffle(self.order)

    def _encode(self, examples: list[dict], limit: int | None = None) -> list[tuple[list[int], list[int]]]:
        """Jetons + étiquettes ; la perte porte sur la réponse seulement (prompt masqué à -100)."""
        out = []
        for ex in examples:
            m = ex["messages"]
            text = render_prompt(m[0]["content"], m[1]["content"])
            prompt = self.tok(text, add_special_tokens=False)["input_ids"]
            answer = self.tok(m[2]["content"] + "<|im_end|>", add_special_tokens=False)["input_ids"]
            if len(prompt) + len(answer) <= self.p["max_seq_len"]:
                out.append((prompt + answer, [-100] * len(prompt) + answer))
                if limit and len(out) >= limit:
                    break
        return out

    def now(self) -> float:
        return time.monotonic()

    def _batch(self, items):
        t = self.torch
        n = max(len(i) for i, _ in items)
        pad = self.tok.pad_token_id or 0
        ids = t.tensor([i + [pad] * (n - len(i)) for i, _ in items]).cuda()
        lab = t.tensor([la + [-100] * (n - len(la)) for _, la in items]).cuda()
        att = t.tensor([[1] * len(i) + [0] * (n - len(i)) for i, _ in items]).cuda()
        return ids, att, lab

    def _loss(self, ids, att, lab):
        """Perte sur la réponse. Lot de 1 (sans bourrage) : logits calculés sur la fin seulement."""
        if ids.shape[0] != 1:
            return self.model(input_ids=ids, attention_mask=att, labels=lab).loss
        n_ans = int((lab[0] != -100).sum())
        out = self.model(input_ids=ids, attention_mask=att, logits_to_keep=n_ans + 1)
        logits = out.logits[:, :-1].float()
        return self.torch.nn.functional.cross_entropy(logits.reshape(-1, logits.shape[-1]), ids[0, -n_ans:])

    def close(self) -> None:
        import gc

        for name in ("model", "opt", "sched", "scaler", "train", "val"):
            setattr(self, name, None)
        gc.collect()
        self.torch.cuda.empty_cache()

    def train_step(self, step: int) -> float:
        t, p = self.torch, self.p
        self.model.train()
        total = 0.0
        for k in range(p["grad_accum"]):
            base = (step * p["grad_accum"] + k) * p["batch_size"]
            items = [self.train[self.order[(base + j) % len(self.order)]] for j in range(p["batch_size"])]
            ids, att, lab = self._batch(items)
            with t.autocast("cuda", dtype=t.float16, enabled=self.fp16):
                loss = self._loss(ids, att, lab) / p["grad_accum"]
            self.scaler.scale(loss).backward()
            total += loss.item()
        self.scaler.unscale_(self.opt)
        t.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.scaler.step(self.opt)
        self.scaler.update()
        self.sched.step()
        self.opt.zero_grad(set_to_none=True)
        return total

    def evaluate(self, step: int) -> float:
        t = self.torch
        self.model.eval()
        losses = []
        with t.no_grad():
            for item in self.val:
                ids, att, lab = self._batch([item])
                with t.autocast("cuda", dtype=t.float16, enabled=self.fp16):
                    losses.append(self._loss(ids, att, lab).item())
        return sum(losses) / max(1, len(losses))

    def free_gb(self, step: int) -> float | None:
        return None

    def temperature(self, step: int) -> float | None:
        return None

    def save_adapter(self, d: Path) -> None:
        self.model.save_pretrained(d)

    def save_checkpoint(self, d: Path) -> None:
        self.model.save_pretrained(d / "adapter")
        self.torch.save({"opt": self.opt.state_dict(), "sched": self.sched.state_dict(),
                         "scaler": self.scaler.state_dict()}, d / "opt.pt")

    def load_checkpoint(self, d: Path) -> None:
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file

        set_peft_model_state_dict(self.model, load_file(str(d / "adapter" / "adapter_model.safetensors")))
        st = self.torch.load(d / "opt.pt", map_location="cpu", weights_only=True)
        self.opt.load_state_dict(st["opt"])
        self.sched.load_state_dict(st["sched"])
        self.scaler.load_state_dict(st["scaler"])


def _bnb_available() -> bool:
    try:
        import bitsandbytes  # noqa: F401
        import torch

        return torch.cuda.is_available()
    except (ImportError, OSError, RuntimeError):
        return False


def release(backend) -> None:
    """Libère la VRAM d'un moteur avant d'en recréer un (mesure -> essai -> long entraînement)."""
    if hasattr(backend, "close"):
        backend.close()


def make_backend(cfg: RunConfig, train: list[dict], val: list[dict]):
    return SimBackend(cfg) if cfg.simulate else TorchBackend(cfg, train, val)


# --------------------------------------------------------------------------- points de reprise
def _ckpt_dir(cfg: RunConfig) -> Path:
    return cfg.run_dir / "checkpoints"


def list_valid_checkpoints(cfg: RunConfig) -> list[Path]:
    """Points de reprise complets (marqueur COMPLETE écrit en dernier), du plus ancien au plus récent."""
    root = _ckpt_dir(cfg)
    if not root.is_dir():
        return []
    return sorted(d for d in root.glob("step-*") if (d / "COMPLETE").is_file())


def save_checkpoint(cfg: RunConfig, backend, state: dict, keep: int) -> Path:
    d = _ckpt_dir(cfg) / f"step-{state['step']:07d}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    backend.save_checkpoint(d)
    (d / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (d / "COMPLETE").write_text("ok", encoding="utf-8")  # écrit en dernier : validité atomique
    for old in list_valid_checkpoints(cfg)[:-keep]:
        shutil.rmtree(old)
    for partial in _ckpt_dir(cfg).glob("step-*"):
        if not (partial / "COMPLETE").is_file():
            shutil.rmtree(partial)
    return d


# --------------------------------------------------------------------------- orchestration
def _guard(cfg: RunConfig, backend, loss: float, state: dict, stop: guards.StopFlag) -> str | None:
    g = guards.GuardConfig(cfg.min_free_gb, cfg.max_gpu_temp)
    step = state["step"]

    def free_fn(path: Path) -> float:
        override = backend.free_gb(step)
        return override if override is not None else guards.free_gb(path)

    def temp_fn() -> float | None:
        t = backend.temperature(step)
        return t if t is not None else (None if backend.simulated else guards.gpu_temperature())

    return guards.check_all(loss, state.get("initial_loss"), cfg.run_dir, g,
                            free_fn=free_fn, temp_fn=temp_fn, stop=stop)


def _base_dir(cfg: RunConfig) -> Path | None:
    """Dossier local du modèle de base (cache Hugging Face) : requis pour convertir l'adaptateur."""
    if cfg.simulate:
        return None
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(cfg.profile["base_model"]))


def run_training(cfg: RunConfig, stop: guards.StopFlag | None = None) -> int:
    """Exécute toutes les étapes ; retourne un code de sortie (voir l'en-tête du module)."""
    stop = stop or guards.StopFlag()
    p = cfg.profile
    train = read_jsonl(cfg.train_path)
    val = read_jsonl(cfg.val_path) if cfg.val_path else []
    cfg.run_dir.mkdir(parents=True, exist_ok=True)
    data_files = {"train": cfg.train_path, **({"val": cfg.val_path} if cfg.val_path else {})}
    params = {**p, "budget_hours": cfg.budget_hours, "save_every_min": cfg.save_every_min,
              "min_free_gb": cfg.min_free_gb, "max_gpu_temp": cfg.max_gpu_temp,
              "profile_name": p.get("name"), "n_train": len(train), "n_val": len(val)}
    log = RunLog(cfg.run_dir, cfg.run_id, cfg.seed, params, data_files, cfg.simulate)
    t_start = time.monotonic()

    def finish(status: str, code: int, reason: str | None = None, clock: float | None = None) -> int:
        log.finish(status, clock if clock is not None else time.monotonic() - t_start, reason)
        return code

    problem = check_data_policy(p, train + val)
    if problem:
        return finish("data_refused", DATA_REFUSED, problem)

    steps = total_steps(len(train), p)
    ckpts = list_valid_checkpoints(cfg)
    state = {"step": 0, "initial_loss": None, "best_eval": None, "bad_evals": 0, "elapsed": 0.0}

    if not ckpts:
        # (1) mesure de 50 pas -> estimation -> refus si au-dessus du budget
        backend = make_backend(cfg, train, val)
        n_measure = min(p.get("measure_steps", MEASURE_STEPS), steps)
        t0 = backend.now()
        for i in range(n_measure):
            backend.train_step(i)
            if (i + 1) % 10 == 0:
                print(f"[mesure] {i + 1}/{n_measure} pas, {(backend.now() - t0) / (i + 1):.1f} s/pas", flush=True)
        per_step = (backend.now() - t0) / n_measure
        estimate_h = per_step * steps / 3600
        log.phase("measure", steps_measured=n_measure, seconds_per_step=round(per_step, 3),
                  total_steps=steps, estimate_hours=round(estimate_h, 3),
                  budget_hours=cfg.budget_hours)
        if estimate_h > cfg.budget_hours:
            return finish("refused_budget", REFUSED_BUDGET,
                          f"durée estimée {estimate_h:.1f} h > budget {cfg.budget_hours} h")
        # (2) essai sur 1 % des pas, puis export test AVANT le long entraînement
        release(backend)
        backend = make_backend(cfg, train, val)
        n_trial = max(2, math.ceil(0.01 * steps))
        trial_state = {"step": 0, "initial_loss": None}
        for i in range(n_trial):
            trial_state["step"] = i
            loss = backend.train_step(i)
            if trial_state["initial_loss"] is None:
                trial_state["initial_loss"] = loss
            why = _guard(cfg, backend, loss, trial_state, stop)
            if why:
                return finish("stopped", STOPPED, f"essai : {why}", backend.now())
        trial_dir = cfg.run_dir / "trial"
        backend.save_adapter(trial_dir / "adapter")
        release(backend)  # la VRAM doit être libre pour le test d'import dans Ollama
        try:
            export_gguf.export(trial_dir / "adapter", trial_dir / "export", cfg.base_tag,
                               simulate=cfg.simulate, base_model_dir=_base_dir(cfg),
                               ollama_tag=None if cfg.simulate else f"{cfg.ollama_tag}-trial")
        except export_gguf.ExportError as e:
            log.phase("trial", steps=n_trial, export_ok=False)
            return finish("export_failed", EXPORT_FAILED, str(e))
        log.phase("trial", steps=n_trial, data_fraction=0.01, export_ok=True)
        if cfg.stop_after_trial:
            return finish("trial_only", OK, "essai + export test terminés (--stop-after-trial)")
        backend = make_backend(cfg, train, val)  # repart de zéro pour le long entraînement
    else:
        backend = make_backend(cfg, train, val)
        last = ckpts[-1]
        state = json.loads((last / "state.json").read_text("utf-8"))
        backend.load_checkpoint(last)
        log.data["resumed_from_step"] = state["step"]
        log.phase("resume", from_checkpoint=last.name, step=state["step"])

    # (3) long entraînement
    clock0 = backend.now() - state["elapsed"]
    last_save = backend.now()
    eval_every = p["eval_every_steps"]
    while state["step"] < steps:
        loss = backend.train_step(state["step"])
        state["step"] += 1
        state["elapsed"] = backend.now() - clock0
        if state["step"] % 5 == 0:
            print(f"[pas {state['step']}/{steps}] perte {loss:.4f} écoulé {state['elapsed'] / 60:.1f} min", flush=True)
        if state["initial_loss"] is None and not math.isnan(loss):
            state["initial_loss"] = loss
        why = _guard(cfg, backend, loss, state, stop)
        if why:
            save_checkpoint(cfg, backend, state, p["keep_checkpoints"])
            return finish("stopped", STOPPED, why, state["elapsed"])
        if state["step"] % eval_every == 0:
            ev = backend.evaluate(state["step"])
            log.metric(state["step"], train_loss=round(loss, 5), eval_loss=round(ev, 5))
            best = state["best_eval"]
            if best is None or ev < best - 1e-4:
                state["best_eval"], state["bad_evals"] = ev, 0
            else:
                state["bad_evals"] += 1
            if state["bad_evals"] >= p["early_stop_patience"]:
                log.phase("early_stop", step=state["step"], best_eval=state["best_eval"])
                break
        if backend.now() - last_save >= cfg.save_every_min * 60:
            save_checkpoint(cfg, backend, state, p["keep_checkpoints"])
            last_save = backend.now()
    save_checkpoint(cfg, backend, state, p["keep_checkpoints"])
    backend.save_adapter(cfg.run_dir / "adapter")
    release(backend)
    try:
        export_gguf.export(cfg.run_dir / "adapter", cfg.run_dir / "export", cfg.base_tag,
                           simulate=cfg.simulate, base_model_dir=_base_dir(cfg),
                           ollama_tag=None if cfg.simulate else cfg.ollama_tag)
    except export_gguf.ExportError as e:
        return finish("export_failed", EXPORT_FAILED, str(e), state["elapsed"])
    log.phase("final", steps=state["step"], best_eval=state["best_eval"])
    return finish("completed", OK, None, state["elapsed"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--profile", default="pc-nuit", help="colab | pc-nuit | chemin .yaml")
    ap.add_argument("--train", type=Path, default=Path("training/data/train.jsonl"))
    ap.add_argument("--val", type=Path, default=Path("training/data/val.jsonl"))
    ap.add_argument("--run-id", default=time.strftime("run-%Y%m%d-%H%M%S"),
                    help="réutiliser un identifiant existant = reprise automatique")
    ap.add_argument("--runs-dir", type=Path, default=Path("training/runs"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--budget-hours", type=float)
    ap.add_argument("--save-every-min", type=float)
    ap.add_argument("--min-free-gb", type=float)
    ap.add_argument("--max-gpu-temp", type=float)
    ap.add_argument("--base-tag", default="qwen3:1.7b")
    ap.add_argument("--measure-steps", type=int, help="pas de la mesure (défaut : profil ou 50)")
    ap.add_argument("--ollama-tag", default="cadrage-lora")
    ap.add_argument("--stop-after-trial", action="store_true", help="s'arrête après l'essai 1 % et l'export test")
    ap.add_argument("--simulate", action="store_true", help="boucle factice : ni torch ni GPU")
    ap.add_argument("--sim-step-seconds", type=float, default=30.0)
    for name in ("nan-at", "kill-at", "disk-full-at", "hot-at", "plateau-at"):
        ap.add_argument(f"--sim-{name}", type=int)
    a = ap.parse_args(argv)
    profile = load_profile(a.profile)
    if a.measure_steps:
        profile["measure_steps"] = a.measure_steps
    pick = lambda cli, key: cli if cli is not None else profile[key]
    cfg = RunConfig(
        profile=profile, run_id=a.run_id, runs_dir=a.runs_dir, train_path=a.train,
        val_path=a.val if a.val.exists() else None, seed=a.seed,
        budget_hours=pick(a.budget_hours, "budget_hours"),
        save_every_min=pick(a.save_every_min, "save_every_min"),
        min_free_gb=pick(a.min_free_gb, "min_free_gb"),
        max_gpu_temp=pick(a.max_gpu_temp, "max_gpu_temp"),
        simulate=a.simulate, base_tag=a.base_tag, ollama_tag=a.ollama_tag,
        stop_after_trial=a.stop_after_trial,
        sim={"step_seconds": a.sim_step_seconds, "nan_at": a.sim_nan_at, "kill_at": a.sim_kill_at,
             "disk_full_at": a.sim_disk_full_at, "hot_at": a.sim_hot_at,
             "plateau_at": a.sim_plateau_at})
    stop = guards.StopFlag()
    stop.install()
    code = run_training(cfg, stop)
    print(f"Fin de l'entraînement : code {code} (voir {cfg.run_dir / 'run.json'})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
