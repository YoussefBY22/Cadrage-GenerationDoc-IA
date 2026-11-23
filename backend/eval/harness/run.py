"""Exécution d'une configuration d'évaluation : `python -m eval.harness.run --config eval/configs/sim.yaml`.

Corpus B4 généré dans un dossier temporaire, ingéré par les services B5, puis mesures de 08 §6.
Résultat : `<out>/<date>-<config>.json` (versions, graines, paramètres, métriques, durée).
"""

import argparse
import contextlib
import json
import platform
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from app import __version__
from app.config import Settings
from app.domain import ids as ids_module
from app.domain.retrieval import Passage
from app.domain.workflow import CurrentUser
from app.generation.llm_schemas import LLMSection
from app.generation.prompting import build_section_prompt, estimate_tokens
from app.generation.relevance import below_threshold
from app.generation.template_loader import SectionSpec, load_template
from app.ingest import parse
from app.llm import FakeProvider, build_provider
from app.services import findings as findings_service
from app.services import ingestion, roadmap_service
from app.services.generation import call_model, new_nonce
from app.services.search import SearchService
from app.storage import build_repository
from app.verification import resolve_labels, verify_section
from eval.corpus.generate import generate
from eval.harness import metrics as M
from eval.harness import simulate
from eval.harness.bootstrap import bootstrap_ci

USER = CurrentUser(id="usr_dev", role="admin")


def load_config(path: str | Path) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cfg.setdefault("name", Path(path).stem)
    cfg.setdefault("seeds", [0])
    cfg.setdefault("corpus_seed", 7)
    cfg.setdefault("retrieval", {"enabled": True, "k": 10})
    return cfg


def _rates(cfg: dict, no_evidence_titles: set[str]) -> simulate.Rates:
    return simulate.Rates(**(cfg.get("simulation") or {}), no_evidence_titles=frozenset(no_evidence_titles))


def _provider(cfg: dict, seed: int, titles: set[str]):
    """Fournisseur de génération : modèle simulé (provider fake) ou réel (ollama)."""
    if cfg.get("provider", "fake") == "fake":
        return FakeProvider(handler=simulate.make_handler(_rates(cfg, titles), seed))
    return build_provider(Settings(llm_provider=cfg["provider"], **cfg.get("settings", {})))


class _VramSampler:
    """Relève la mémoire GPU utilisée toutes les 2 s pendant l'exécution (pic, en Mo)."""

    def __init__(self) -> None:
        self.peak: int | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            v = _vram_mb()
            if v is not None:
                self.peak = max(self.peak or 0, v)
            self._stop.wait(2.0)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(timeout=15)


def _vram_mb() -> int | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, check=True).stdout
        return max(int(x) for x in out.split())
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def _spec(key: str, title: str, queries: list[str], max_sentences: int = 3) -> SectionSpec:
    return SectionSpec(key=key, title=title, instructions=title, queries=queries,
                       min_sources=1, max_sentences=max_sentences)


def _generate(provider, search, dossier: str, spec: SectionSpec, passages: list[Passage],
              gate: float = 0.0) -> dict:
    """Une génération de section avec la chaîne réelle (prompt, appel, vérification).

    ``gate`` : porte de pertinence (seuil de cosinus, 0 = désactivée) ; sous le seuil, refus SANS appel au modèle,
    comme dans l'application (app.generation.relevance).
    """
    if search is not None and gate > 0 and below_threshold(search, dossier, spec.queries, gate)[0]:
        passages = []
    if search is not None and len(passages) < spec.min_sources:
        return {"refused": True, "first_try": True, "latency_ms": 0, "tokens_out": 0,
                "tpv": 1.0, "sentences": [], "cited": 0, "found": 0, "texts": []}
    prompt = build_section_prompt(spec, passages, nonce=new_nonce())
    llm, attempts, latency, _err = call_model(provider, prompt, LLMSection)
    if llm is None:
        return {"refused": False, "first_try": False, "latency_ms": latency, "tokens_out": 0,
                "tpv": 0.0, "sentences": [], "cited": 0, "found": 0, "texts": []}
    draft = resolve_labels(llm, passages, section_key=spec.key)
    report = verify_section(draft, {p.chunk.id: p.chunk for p in passages}, dossier_id=dossier)
    bad = {i.sentence_index for i in report.issues if i.severity == "blocking"}
    return {
        "refused": draft.status == "insufficient_evidence", "first_try": attempts == 1,
        "latency_ms": latency, "tokens_out": estimate_tokens(llm.model_dump_json()),
        "tpv": report.tpv,
        "sentences": [(len(s.source_ids), i in bad) for i, s in enumerate(draft.sentences)],
        "cited": sum(c.numbers_cited for c in report.checks),
        "found": sum(c.numbers_found for c in report.checks),
        "texts": [s.text for s in draft.sentences],
    }


def _ingest(repo, provider, search, settings, dossier: str, paths: list[Path]) -> None:
    for p in paths:
        ingestion.ingest(repo, provider, dossier, p.name, p.read_bytes(), USER,
                         search=search, settings=settings)


def _retrieval_metrics(search, gold, dossiers: dict[str, str], k: int) -> dict:
    ranks = []
    for q in gold.queries:
        found = search.search(dossiers[q.institution], [q.text], k)
        ranks.append(M.first_hit_rank([p.chunk.text for p in found], q.expected_markers))
    return {"recall_at_k": M.recall_at_k(ranks, k), "mrr": M.mrr(ranks)}


def _findings_and_roadmap(repo, provider, dossier: str, inst: str, gold) -> dict:
    out = findings_service.extract(repo, provider, dossier, USER)
    cited = list(dict.fromkeys(i for f in out["findings"] for i in f["source_ids"]))
    texts = [c.text for c in repo.get_chunks(dossier, cited).values()]
    cov = M.finding_coverage([f.evidence_markers for f in gold.findings if f.institution == inst],
                             texts)
    repo.save_findings(dossier, [f.model_copy(update={"validated": True})
                                 for f in repo.list_findings(dossier)])
    res = {"finding_coverage": cov, "dependency_cycles": None, "dependency_recall": None}
    try:
        road = roadmap_service.generate(repo, provider, dossier, USER)["roadmap"]
    except Exception:  # noqa: BLE001 — un modèle réel peut échouer : la métrique reste vide
        return res
    num = {}
    for it in road["items"]:
        m = re.search(r"\bI(\d+)\b", it["initiative"]["title"])
        if m:
            num[it["initiative"]["id"]] = f"{inst}-I{m.group(1)}"
    produced = {(num[it["initiative"]["id"]], num[d]) for it in road["items"]
                for d in it["initiative"]["depends_on"]
                if it["initiative"]["id"] in num and d in num}
    gold_edges = {(d.source, d.target) for d in gold.dependencies if d.institution == inst}
    res |= {"dependency_cycles": len(road["cycles"]),
            "dependency_recall": M.dependency_recall(gold_edges, produced)}
    return res


@contextlib.contextmanager
def _deterministic_ids(seed: int):
    """Identifiants reproductibles (les égalités de score se départagent par id : sinon l'ordre des
    passages varie d'une exécution à l'autre)."""
    rng = random.Random(seed)
    real = ids_module.uuid.uuid4
    ids_module.uuid.uuid4 = lambda: uuid.UUID(int=rng.getrandbits(128), version=4)
    try:
        yield
    finally:
        ids_module.uuid.uuid4 = real


def run_config(cfg: dict, out_dir: str | Path | None = None) -> dict:
    with _deterministic_ids(cfg["corpus_seed"]), _VramSampler() as vram:
        result = _run(cfg, out_dir)
    if vram.peak is not None:  # pic mesuré pendant toute l'exécution (et non en fin de course)
        result["metrics"]["vram_max_mb"] = {"mean": vram.peak}
        if out_dir is not None:
            out = Path(out_dir) / f"{result['date']}-{cfg['name']}.json"
            out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


class _IngestSettings:
    """Réglages d'ingestion : ceux de l'application + le préfixe de passage propre au modèle."""

    def __init__(self, base: Settings, passage_prefix: str) -> None:
        self._base = base
        self.embedding_passage_prefix = passage_prefix

    def __getattr__(self, name):
        return getattr(self._base, name)


def _run(cfg: dict, out_dir: str | Path | None) -> dict:
    t0 = time.perf_counter()
    use_ret = bool(cfg["retrieval"].get("enabled", True))
    k = int(cfg["retrieval"].get("k", 10))
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        gold = generate(cfg["corpus_seed"], tmp / "corpus")
        insts = list(dict.fromkeys(d.institution for d in gold.documents))
        insts = insts[: cfg.get("subset", {}).get("institutions", len(insts))]
        no_ev_titles = {n.section_request for n in gold.no_evidence}
        settings = Settings(storage_url=f"sqlite+pysqlite:///{(tmp / 'eval.db').as_posix()}",
                            auth_mode="dev", upload_dir=str(tmp / "up"))
        repo = build_repository(settings)
        # Vectorisation (ingestion et recherche) : faux modèle en simulation, vrai modèle d'embeddings
        # (ex. bge-m3) quand le fournisseur est réel — sinon rappel@10 ne mesurerait rien de réel.
        real = cfg.get("provider", "fake") != "fake"
        base = build_provider(Settings(llm_provider=cfg["provider"], **cfg.get("settings", {})))             if real else FakeProvider()
        if real:
            settings = _IngestSettings(settings, cfg.get("settings", {}).get(
                "ollama_embedding_passage_prefix", ""))
        search = SearchService(repo, base)
        dossiers: dict[str, str] = {}
        for inst in insts:
            dossiers[inst] = repo.create_dossier(inst, inst, "fr", "usr_dev")
            repo.add_member(dossiers[inst], "usr_dev", "consultant")
            files = [tmp / "corpus" / next(iter(d.paths.values()))
                     for d in gold.documents if d.institution == inst]
            _ingest(repo, base, search, settings, dossiers[inst], files)
        gold = gold.model_copy(update={"queries": [q for q in gold.queries if q.institution in insts]})
        trap_dossier = repo.create_dossier("pièges", "pièges", "fr", "usr_dev")
        repo.add_member(trap_dossier, "usr_dev", "consultant")
        trap_files = [tmp / "corpus" / t.path for t in gold.traps]
        _ingest(repo, base, search, settings, trap_dossier, trap_files)

        # Sections : gabarits ToR/CdC par institution + sections « preuve » ; puis « sans preuve »
        main: list[tuple[str, SectionSpec]] = []
        for inst in insts:
            for typ in ("tor", "cdc"):
                main += [(inst, s) for s in load_template(typ, "fr").sections]
        proof = [(q.institution, _spec(q.id, f"Fait : {q.text}", [q.text, f"{q.text} valeur observée"]))
                 for q in gold.queries]
        noev = [(insts[0], _spec(n.id, n.section_request, [n.section_request, n.forbidden_keyword]))
                for n in gold.no_evidence]
        traps = []
        for t, f in zip(gold.traps, trap_files, strict=True):
            head = parse(f.name, f.read_bytes()).blocks[0].text[:150]
            traps.append((trap_dossier, _spec(t.id, f"Piège {t.kind}", [head, f"{head} résumé"])))

        def passages_for(dossier, spec):
            return search.search(dossier, spec.queries, k) if use_ret else []

        cache = {(d, s.key): passages_for(dossiers.get(d, d), s) for d, s in main + proof + noev + traps}
        sections_all = [("main", d, s) for d, s in main] + [("proof", d, s) for d, s in proof] + \
                       [("noev", d, s) for d, s in noev]

        gate = float(cfg.get("settings", {}).get("relevance_threshold") or 0.0)
        per_seed: list[dict] = []
        tpv_pool: list[float] = []
        latencies: list[float] = []
        by_kind_lat: list[tuple[str, float]] = []
        tokens = 0
        for seed in cfg["seeds"]:
            prov = _provider(cfg, seed, no_ev_titles)
            recs = []
            for kind, d, s in sections_all:
                dossier = dossiers[d]
                r = _generate(prov, search if use_ret else None, dossier, s, cache[(d, s.key)], gate)
                recs.append((kind, r))
                if real:
                    print(f"[seed {seed}] {len(recs)}/{len(sections_all)} {kind} {s.key} "
                          f"{r['latency_ms']} ms tpv={r['tpv']:.2f} refus={r['refused']}",
                          file=sys.stderr, flush=True)
            scored = [r for kind, r in recs if kind != "noev"]
            tpv_pool += [r["tpv"] for kind, r in recs if kind in ("main", "proof")]
            latencies += [r["latency_ms"] for _, r in recs if r["latency_ms"]]
            by_kind_lat += [(kind, r["latency_ms"]) for kind, r in recs if r["latency_ms"]]
            tokens += sum(r["tokens_out"] for _, r in recs)
            expected = [kind == "noev" for kind, _ in recs if kind in ("proof", "noev")]
            refused = [r["refused"] for kind, r in recs if kind in ("proof", "noev")]
            missed, false = M.refusal_rates(expected, refused)
            attacks = []
            for d, s in traps:
                r = _generate(prov, search if use_ret else None, d, s, cache[(d, s.key)], gate)
                attacks.append(any(simulate.CANARY in t for t in r["texts"]))
            row = {
                "tpv": M.mean_sd([r["tpv"] for kind, r in recs if kind in ("main", "proof")])[0],
                "citation_validity": M.citation_validity([x for r in scored for x in r["sentences"]]),
                "number_fidelity": M.number_fidelity(sum(r["cited"] for r in scored),
                                                     sum(r["found"] for r in scored)),
                "structure_validity": M.structure_validity([r["first_try"] for _, r in recs]),
                "missed_refusals": missed, "false_refusals": false,
                "tpv_answered": M.mean_sd([r["tpv"] for kind, r in recs
                                           if kind in ("main", "proof") and not r["refused"]])[0],
                "refusal_rate": sum(r["refused"] for _, r in recs) / max(len(recs), 1),
                "attack_success": M.attack_rate(attacks),
            }
            if seed == cfg["seeds"][0] and use_ret:  # constats et feuille de route : 1re graine
                row |= _findings_and_roadmap(repo, prov, dossiers[insts[0]], insts[0], gold)
            per_seed.append(row)
        ret = _retrieval_metrics(search, gold, dossiers, k) if use_ret else {}
        repo.engine.dispose()

    agg: dict[str, dict] = {}
    for key in {k2 for row in per_seed for k2 in row}:
        vals = [row[key] for row in per_seed if row.get(key) is not None]
        mean, sd = M.mean_sd(vals) if vals else (None, None)
        agg[key] = {"mean": mean, "sd": sd, "values": vals}
    for key, val in ret.items():
        agg[key] = {"mean": val, "sd": 0.0, "values": [val]}
    secs = max(time.perf_counter() - t0, 1e-9)
    agg["latency_p50_ms"] = {"mean": M.percentile(latencies, 50)}
    agg["latency_p95_ms"] = {"mean": M.percentile(latencies, 95)}
    for kind in ("main", "proof", "noev"):
        agg[f"latency_p50_ms_{kind}"] = {"mean": M.percentile(
            [v for k2, v in by_kind_lat if k2 == kind], 50)}
    agg["tokens_per_s"] = {"mean": tokens / secs}
    agg["vram_max_mb"] = {"mean": _vram_mb()}
    result = {
        "config": cfg["name"], "date": datetime.now(UTC).strftime("%Y%m%d"),
        "simulation": cfg.get("provider", "fake") == "fake",
        "notice": simulate.NOTICE if cfg.get("provider", "fake") == "fake" else None,
        "versions": {"app": __version__, "python": platform.python_version(),
                     "provider": cfg.get("provider", "fake"), "model": cfg.get("model"),
                     "adapter": cfg.get("adapter")},
        "seeds": cfg["seeds"], "corpus_seed": cfg["corpus_seed"],
        "params": {"retrieval": cfg["retrieval"], "simulation": cfg.get("simulation"),
                   "subset": cfg.get("subset")},
        "metrics": agg, "tpv_sections": tpv_pool, "tpv_ci95": bootstrap_ci(tpv_pool, 1000, 0),
        "n_sections": len(tpv_pool), "duration_s": round(secs, 2),
    }
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{result['date']}-{cfg['name']}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="eval/results/")
    args = ap.parse_args()
    res = run_config(load_config(args.config), args.out)
    if res["notice"]:
        print(res["notice"].upper())
    m = res["metrics"]
    print(f"{res['config']} : TPV {m['tpv']['mean']:.3f} IC95 "
          f"[{res['tpv_ci95'][0]:.3f}, {res['tpv_ci95'][1]:.3f}] sur {res['n_sections']} sections "
          f"en {res['duration_s']} s")
    for key in ("refusal_rate", "missed_refusals", "false_refusals", "citation_validity",
                "number_fidelity", "structure_validity", "recall_at_k", "mrr", "latency_p50_ms",
                "latency_p95_ms", "tokens_per_s", "vram_max_mb"):
        if key in m and m[key].get("mean") is not None:
            print(f"  {key}: {m[key]['mean']:.3f}")


if __name__ == "__main__":
    main()
