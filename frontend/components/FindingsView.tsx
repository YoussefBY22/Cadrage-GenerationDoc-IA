"use client";

import { Check, ChevronRight, ExternalLink, FileText, ListChecks, Pencil, Sparkles } from "lucide-react";
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

/** Liste des constats : valider, corriger le texte, ouvrir les sources dans le panneau de droite. */
const pages = (r: SourceRef) =>
  r.page_end && r.page_start && r.page_end !== r.page_start ? `${r.page_start}–${r.page_end}` : `${r.page_start ?? "?"}`;

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
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const dossier = useDossier(dossierId);

  const load = useCallback(() => {
    api
      .listFindings(dossierId)
      .then(setFindings)
      .catch((e) => setError(guard(e)));
  }, [dossierId, guard]);

  useEffect(load, [load]);

  const patch = async (f: Finding, body: { text?: string; validated?: boolean }) => {
    setError(null);
    try {
      const updated = await api.patchFinding(f.id, body);
      setFindings((cur) => cur?.map((x) => (x.id === f.id ? { ...updated, sources: x.sources } : x)) ?? cur);
      setEditing(null);
    } catch (e) {
      setError(guard(e));
    }
  };

  const job = useJob(dossierId, "findings", (j) => {
    if (j.result && "coverage" in j.result) setCoverage(j.result.coverage as Coverage);
    load();
  });
  const busy = job.running;

  const extract = async () => {
    setError(null);
    if (findings && findings.length > 0 && !window.confirm(t.findings.confirmRerun(findings.length))) return;
    await job.start();
  };

  // pendant l'extraction, les constats apparaissent au fil de l'eau
  const done = job.job?.done;
  useEffect(() => {
    if (job.running) load();
  }, [done, job.running, load]);

  const first = (f: Finding): SourceRef | undefined =>
    [...(f.sources ?? [])].sort((a, b) => a.document_rank - b.document_rank || a.ordinal - b.ordinal)[0];
  const sevRank = { high: 0, medium: 1, low: 2 } as const;
  const docs = Array.from(
    new Map((findings ?? []).flatMap((f) => f.sources ?? []).map((r) => [r.document_id, r.filename])).entries(),
  );
  const shown = (findings ?? [])
    .filter((f) => filter === "all" || f.severity === filter)
    .filter((f) => doc === "all" || (f.sources ?? []).some((r) => r.document_id === doc))
    .sort((a, b) => {
      const ra = first(a), rb = first(b);
      const byDoc = (ra?.document_rank ?? 99) - (rb?.document_rank ?? 99) || (ra?.ordinal ?? 0) - (rb?.ordinal ?? 0);
      return order === "document" ? byDoc : sevRank[a.severity] - sevRank[b.severity] || byDoc;
    });
  const validated = findings?.filter((f) => f.validated).length ?? 0;

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
          {findings && findings.length > 0 && (
            <>
              <span className="badge approved plain">
                {validated}/{findings.length}
              </span>
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
              {docs.length > 1 && (
                <select value={doc} onChange={(e) => setDoc(e.target.value)} aria-label={t.findings.docFilter}>
                  <option value="all">{t.findings.allDocs}</option>
                  {docs.map(([id, name]) => (
                    <option key={id} value={id}>{name}</option>
                  ))}
                </select>
              )}
            </>
          )}
          <button className="btn btn-primary" onClick={extract} disabled={busy} title={t.findings.extractHelp}>
            <Sparkles size={16} />
            {t.findings.extract}
          </button>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}
      {job.error && <Alert>{job.error}</Alert>}
      {job.job && <JobPanel job={job.job} onCancel={() => void job.cancel()} onClose={job.dismiss} />}
      {coverage && (
        <p className="muted" data-testid="coverage" style={{ marginTop: 0 }}>
          {t.coeur.coverage.read(coverage.chunks_read, coverage.chunks_total)}
          {coverage.chunks_failed > 0 && ` · ${t.coeur.coverage.failed(coverage.chunks_failed)}`}
          {coverage.excluded.length > 0 &&
            ` · ${t.coeur.coverage.excluded} : ${coverage.excluded
              .map((e) => `${e.filename} (${t.coeur.roles[e.role] ?? e.role} : ${e.reason})`)
              .join(" ; ")}`}
        </p>
      )}
      {findings === null && !error && <p className="muted">{t.common.loading}</p>}
      <div className={`split${source ? " with-panel" : ""}`}>
        <section>
          {findings?.length === 0 && <Empty icon={ListChecks} label={t.findings.none} />}
          <ul className="cards">
            {shown.map((f) => (
              <li
                key={f.id}
                className={`card finding sev-${f.severity}${source?.finding === f.id ? " selected" : ""}`}
                data-testid={`finding-${f.id}`}
              >
                <label style={{ display: "flex", alignItems: "flex-start", paddingTop: 2 }}>
                  <input
                    type="checkbox"
                    checked={f.validated}
                    onChange={(e) => patch(f, { validated: e.target.checked })}
                    aria-label={f.validated ? t.findings.unvalidate : t.findings.validate}
                  />
                </label>
                <div className="finding-body">
                  <div className="finding-meta">
                    <span className={`badge ${f.validated ? "approved" : "draft"}`}>
                      {f.validated ? t.findings.validated : t.findings.draft}
                    </span>
                    <span className={`badge sev-${f.severity}`}>{t.findings.severity[f.severity]}</span>
                    <span className="tag">{f.theme}</span>
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
                  <div className="row" style={{ gap: 6 }}>
                    {(f.sources?.length ? f.sources : f.source_ids.map((id) => ({ chunk_id: id }) as SourceRef)).map((r, i) => (
                      <span key={r.chunk_id} className="source-ref">
                        <button
                          className="link"
                          title={t.findings.showPassage}
                          onClick={() => setSource({ chunk: r.chunk_id, finding: f.id })}
                        >
                          <FileText size={13} />
                          {r.filename
                            ? `${t.findings.proof} ${i + 1} · ${r.filename}${r.page_start ? ` | ${t.findings.page} ${pages(r)}` : ""}`
                            : `${t.findings.proof} ${i + 1}`}
                        </button>
                        {r.document_id && (
                          <a
                            className="link"
                            href={`/documents/${r.document_id}?page=${r.page_start ?? 1}&finding=${f.id}`}
                            target="cadrage-document"
                            rel="noopener"
                            title={t.findings.openInDoc}
                          >
                            <ExternalLink size={13} />
                            {t.findings.openInDoc}
                          </a>
                        )}
                      </span>
                    ))}
                    {editing !== f.id && (
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ marginLeft: "auto" }}
                        onClick={() => {
                          setEditing(f.id);
                          setDraft(f.text);
                        }}
                      >
                        <Pencil size={13} />
                        {t.findings.edit}
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
        {source && <SourcePanel chunkId={source.chunk} onClose={() => setSource(null)} />}
      </div>
    </>
  );
}
