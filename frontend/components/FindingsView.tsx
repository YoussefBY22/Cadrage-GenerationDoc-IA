"use client";

import {
  Ban,
  Check,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FileText,
  ListChecks,
  Pencil,
  Quote,
  RotateCcw,
  Sparkles,
  Split,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import JobPanel from "@/components/JobPanel";
import SourcePanel from "@/components/SourcePanel";
import { Alert, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { Coverage, Finding, Severity, SourceRef } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useDossier } from "@/lib/useDossier";
import { useGuard } from "@/lib/useGuard";
import { useJob } from "@/lib/useJob";
import { useViewerOpener } from "@/lib/viewerLink";

const pages = (r: SourceRef) =>
  r.page_end && r.page_start && r.page_end !== r.page_start ? `${r.page_start}–${r.page_end}` : `${r.page_start ?? "?"}`;

const first = (f: Finding): SourceRef | undefined =>
  [...(f.sources ?? [])].sort((a, b) => a.document_rank - b.document_rank || a.ordinal - b.ordinal)[0];

/** Constats : lire, vérifier la preuve, valider, corriger, écarter, défusionner. */
export default function FindingsView({ dossierId }: { dossierId: string }) {
  const guard = useGuard();
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [source, setSource] = useState<{ chunk: string; finding: string } | null>(null);
  const [filter, setFilter] = useState<Severity | "all">("all");
  const [order, setOrder] = useState<"document" | "severity">("document");
  const [doc, setDoc] = useState<string>("all");
  const [view, setView] = useState<"active" | "discarded">("active");
  const [reco, setReco] = useState<string>("all");
  const [openQuote, setOpenQuote] = useState<Record<string, boolean>>({});
  const [openMerged, setOpenMerged] = useState<Record<string, boolean>>({});
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const dossier = useDossier(dossierId);
  const viewer = useViewerOpener();

  const load = useCallback(() => {
    api
      .listFindings(dossierId)
      .then(setFindings)
      .catch((e) => setError(guard(e)));
  }, [dossierId, guard]);

  useEffect(load, [load]);
  useEffect(() => {
    const r = new URLSearchParams(window.location.search).get("reco");
    if (r) setReco(r);
  }, []);

  const patch = async (f: Finding, body: { text?: string; validated?: boolean }) => {
    setError(null);
    try {
      const updated = await api.patchFinding(f.id, body);
      setFindings((cur) => cur?.map((x) => (x.id === f.id ? { ...x, ...updated, sources: x.sources } : x)) ?? cur);
      setEditing(null);
    } catch (e) {
      setError(guard(e));
    }
  };

  const act = async (f: Finding, action: "unmerge" | "restore" | "discard" | "original", reason?: string) => {
    setError(null);
    try {
      await api.findingAction(f.id, action, reason ? { reason } : {});
      load();
    } catch (e) {
      setError(guard(e));
    }
  };

  const extractJob = useJob(dossierId, "findings", (j) => {
    if (j.result && "coverage" in j.result) setCoverage(j.result.coverage as Coverage);
    load();
  });
  const cleanJob = useJob(dossierId, "clean", () => load());
  const busy = extractJob.running || cleanJob.running;

  const extract = async () => {
    setError(null);
    if (findings && findings.length > 0 && !window.confirm(t.findings.confirmRerun(findings.length))) return;
    await extractJob.start();
  };
  const clean = async () => {
    if (!window.confirm(t.findings.confirmClean(toClean))) return;
    await cleanJob.start();
  };

  // pendant une tâche, les constats apparaissent ou changent au fil de l'eau
  const progress = (extractJob.job?.done ?? 0) + (cleanJob.job?.done ?? 0);
  useEffect(() => {
    if (busy) load();
  }, [progress, busy, load]);

  const all = findings ?? [];
  const toClean = all.filter((f) => !f.kind).length;
  const mergedInto = (id: string) => all.filter((x) => x.merged_into === id);
  const top = all.filter((f) => !f.merged_into);
  const discarded = top.filter((f) => f.status === "discarded");
  const active = top.filter((f) => f.status !== "discarded");
  const recos = Array.from(
    new Map(active.flatMap((f) => f.recommendations ?? []).map((r) => [r.id, r.number])).entries(),
  ).sort((a, b) => (a[1] ?? 99) - (b[1] ?? 99));
  const sevRank = { high: 0, medium: 1, low: 2 } as const;
  const docs = Array.from(new Map(all.flatMap((f) => f.sources ?? []).map((r) => [r.document_id, r.filename])).entries());
  const shown = (view === "active" ? active : discarded)
    .filter((f) => filter === "all" || f.severity === filter)
    .filter((f) => doc === "all" || (f.sources ?? []).some((r) => r.document_id === doc))
    .filter((f) =>
      reco === "all" ? true : reco === "none" ? !(f.recommendations?.length) : (f.recommendations ?? []).some((r) => r.id === reco),
    )
    .sort((a, b) => {
      const ra = first(a), rb = first(b);
      const byDoc = (ra?.document_rank ?? 99) - (rb?.document_rank ?? 99) || (ra?.ordinal ?? 0) - (rb?.ordinal ?? 0);
      return order === "document" ? byDoc : sevRank[a.severity] - sevRank[b.severity] || byDoc;
    });
  const validated = active.filter((f) => f.validated).length;

  const proofLinks = (f: Finding) =>
    (f.sources?.length ? f.sources : f.source_ids.map((id) => ({ chunk_id: id }) as SourceRef)).map((r, i) => (
      <span key={r.chunk_id} className="source-ref">
        <button className="link" title={t.findings.showPassage} onClick={() => setSource({ chunk: r.chunk_id, finding: f.id })}>
          <FileText size={13} />
          {r.filename
            ? `${t.findings.proof} ${i + 1} · ${r.filename}${r.page_start ? ` | ${t.findings.page} ${pages(r)}` : ""}`
            : `${t.findings.proof} ${i + 1}`}
        </button>
        {r.document_id && (
          <button
            type="button"
            className="link"
            title={t.findings.openInDoc}
            onClick={() => void viewer.open({ docId: r.document_id, page: r.page_start, findingId: f.id })}
          >
            <ExternalLink size={13} />
            {t.findings.openInDoc}
          </button>
        )}
      </span>
    ));

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href="/dossiers">{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
            <Link href={`/dossiers/${dossierId}`}>{dossier?.name ?? "…"}</Link>
            <ChevronRight size={14} />
          </div>
          <h1>{t.findings.title}</h1>
          <p className="page-hint">{t.findings.hint}</p>
        </div>
        <div className="actions">
          {toClean > 0 && (
            <button className="btn" onClick={() => void clean()} disabled={busy} title={t.findings.cleanHelp}>
              <WandSparkles size={16} />
              {t.findings.clean(toClean)}
            </button>
          )}
          <button className="btn btn-primary" onClick={() => void extract()} disabled={busy} title={t.findings.extractHelp}>
            <Sparkles size={16} />
            {t.findings.extract}
          </button>
        </div>
      </div>
      {viewer.modal}
      {error && <Alert>{error}</Alert>}
      {extractJob.error && <Alert>{extractJob.error}</Alert>}
      {cleanJob.error && <Alert>{cleanJob.error}</Alert>}
      {extractJob.job && <JobPanel job={extractJob.job} onCancel={() => void extractJob.cancel()} onClose={extractJob.dismiss} />}
      {cleanJob.job && <JobPanel job={cleanJob.job} onCancel={() => void cleanJob.cancel()} onClose={cleanJob.dismiss} />}
      {coverage && (
        <p className="muted" data-testid="coverage" style={{ marginTop: 0 }}>
          {t.coeur.coverage.read(coverage.chunks_read, coverage.chunks_total)}
          {coverage.chunks_failed > 0 && ` · ${t.coeur.coverage.failed(coverage.chunks_failed)}`}
        </p>
      )}
      {all.length > 0 && (
        <div className="toolbar">
          <div className="filter" role="group" aria-label={t.findings.viewLabel}>
            <button type="button" aria-pressed={view === "active"} onClick={() => setView("active")}>
              {t.findings.activeView(active.length, validated)}
            </button>
            <button type="button" aria-pressed={view === "discarded"} onClick={() => setView("discarded")}>
              {t.findings.discardedView(discarded.length)}
            </button>
          </div>
          <div className="filter" role="group" aria-label={t.findings.sortLabel}>
            {(["document", "severity"] as const).map((o) => (
              <button key={o} type="button" aria-pressed={order === o} onClick={() => setOrder(o)}>
                {t.findings.sort[o]}
              </button>
            ))}
          </div>
          <div className="filter" role="group" aria-label={t.findings.title}>
            {(["all", "high", "medium", "low"] as const).map((s) => (
              <button key={s} type="button" aria-pressed={filter === s} onClick={() => setFilter(s)}>
                {s === "all" ? t.findings.all : t.findings.severity[s]}
              </button>
            ))}
          </div>
          {recos.length > 0 && (
            <select className="mini-select" value={reco} onChange={(e) => setReco(e.target.value)} aria-label={t.findings.recoFilter}>
              <option value="all">{t.findings.allRecos}</option>
              {recos.map(([id, n]) => (
                <option key={id} value={id}>
                  {t.findings.recoN(n)}
                </option>
              ))}
              <option value="none">{t.findings.noReco}</option>
            </select>
          )}
          {docs.length > 1 && (
            <select className="mini-select" value={doc} onChange={(e) => setDoc(e.target.value)} aria-label={t.findings.docFilter}>
              <option value="all">{t.findings.allDocs}</option>
              {docs.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          )}
        </div>
      )}
      {view === "discarded" && <p className="muted">{t.findings.discardedHint}</p>}
      {findings === null && !error && <p className="muted">{t.common.loading}</p>}
      <div className={`split${source ? " with-panel" : ""}`}>
        <section>
          {findings?.length === 0 && <Empty icon={ListChecks} label={t.findings.none} />}
          <ul className="cards">
            {shown.map((f) => {
              const children = mergedInto(f.id);
              return (
                <li
                  key={f.id}
                  className={`card finding sev-${f.severity}${source?.finding === f.id ? " selected" : ""}${f.status === "discarded" ? " discarded" : ""}`}
                  data-testid={`finding-${f.id}`}
                >
                  {f.status !== "discarded" ? (
                    <label style={{ display: "flex", alignItems: "flex-start", paddingTop: 2 }}>
                      <input
                        type="checkbox"
                        checked={f.validated}
                        onChange={(e) => patch(f, { validated: e.target.checked })}
                        aria-label={f.validated ? t.findings.unvalidate : t.findings.validate}
                      />
                    </label>
                  ) : (
                    <span />
                  )}
                  <div className="finding-body">
                    <div className="finding-meta">
                      {f.status === "discarded" ? (
                        <span className="badge rejected">{t.findings.discarded}</span>
                      ) : (
                        <span className={`badge ${f.validated ? "approved" : "draft"}`}>
                          {f.validated ? t.findings.validated : t.findings.draft}
                        </span>
                      )}
                      <span className={`badge sev-${f.severity}`}>{t.findings.severity[f.severity]}</span>
                      {f.kind && f.kind !== "contexte" && <span className="tag">{t.findings.kind[f.kind]}</span>}
                      {(f.recommendations ?? []).map((r) => (
                        <Link key={r.id} className="tag tag-link" href={`/dossiers/${dossierId}/recommendations#${r.id}`} title={t.findings.recoLinkHint(f.paragraph)}>
                          → {t.findings.recoN(r.number)}
                        </Link>
                      ))}
                      {f.paragraph != null && <span className="muted small">§ {f.paragraph}</span>}
                    </div>
                    {editing === f.id ? (
                      <>
                        <textarea
                          value={draft}
                          onChange={(e) => setDraft(e.target.value)}
                          rows={4}
                          aria-label={t.findings.edit}
                          style={{ margin: "8px 0" }}
                        />
                        <div className="row">
                          <button className="btn btn-dark btn-sm" onClick={() => patch(f, { text: draft })}>
                            <Check size={14} />
                            {t.common.save}
                          </button>
                          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>
                            {t.common.cancel}
                          </button>
                        </div>
                      </>
                    ) : (
                      <p>{f.text}</p>
                    )}
                    {f.status === "discarded" && f.discard_reason && <p className="muted small">{t.findings.why} {f.discard_reason}</p>}
                    {f.quote && f.quote !== f.text && (
                      <div className="quote-box">
                        <button type="button" className="link" onClick={() => setOpenQuote((o) => ({ ...o, [f.id]: !o[f.id] }))}>
                          <Quote size={13} />
                          {openQuote[f.id] ? t.findings.hideQuote : t.findings.showQuote}
                          {f.rewritten && <span className="muted"> · {t.findings.rewrittenNote}</span>}
                        </button>
                        {openQuote[f.id] && (
                          <>
                            <blockquote>« {f.quote} »</blockquote>
                            <button type="button" className="btn btn-ghost btn-sm" onClick={() => void act(f, "original")}>
                              <RotateCcw size={13} />
                              {t.findings.useOriginal}
                            </button>
                          </>
                        )}
                      </div>
                    )}
                    <div className="row" style={{ gap: 6 }}>
                      {proofLinks(f)}
                      <span style={{ marginLeft: "auto" }} />
                      {editing !== f.id && f.status !== "discarded" && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => {
                            setEditing(f.id);
                            setDraft(f.text);
                          }}
                        >
                          <Pencil size={13} />
                          {t.findings.edit}
                        </button>
                      )}
                      {f.status === "discarded" ? (
                        <button className="btn btn-ghost btn-sm" onClick={() => void act(f, "restore")}>
                          <RotateCcw size={13} />
                          {t.findings.restore}
                        </button>
                      ) : (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => {
                            const why = window.prompt(t.findings.discardPrompt, "");
                            if (why !== null) void act(f, "discard", why);
                          }}
                        >
                          <Ban size={13} />
                          {t.findings.discard}
                        </button>
                      )}
                    </div>
                    {children.length > 0 && (
                      <div className="merged-box">
                        <button type="button" className="link" onClick={() => setOpenMerged((o) => ({ ...o, [f.id]: !o[f.id] }))}>
                          {openMerged[f.id] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          {t.findings.mergedCount(children.length)}
                        </button>
                        {openMerged[f.id] && (
                          <ul>
                            {children.map((c) => (
                              <li key={c.id}>
                                <p>{c.quote ?? c.text}</p>
                                <div className="row" style={{ gap: 6 }}>
                                  {proofLinks(c)}
                                  <button className="btn btn-ghost btn-sm" style={{ marginLeft: "auto" }} onClick={() => void act(c, "unmerge")}>
                                    <Split size={13} />
                                    {t.findings.unmerge}
                                  </button>
                                </div>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
        {source && <SourcePanel chunkId={source.chunk} onClose={() => setSource(null)} />}
      </div>
    </>
  );
}
