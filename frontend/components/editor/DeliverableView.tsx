"use client";

import WaitNote from "@/components/WaitNote";
import { CheckCheck, ChevronRight, MessageSquare, Sparkles, Save } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import SourcePanel from "@/components/SourcePanel";
import { Alert } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { sectionTitle, t } from "@/lib/i18n";
import { AckBar, ExportBar, TransitionBar } from "./ActionBars";
import { deliverables, type ExportFormat } from "./client";
import { m } from "./i18n";
import SectionEditor from "./SectionEditor";
import {
  TEMPLATE_SECTIONS,
  type CommentInfo,
  type Deliverable,
  type Role,
  type SectionDraft,
  type VersionInfo,
} from "./types";
import VersionsPanel from "./VersionsPanel";

const TYPE_LABEL: Record<string, string> = { tor: "TdR", cdc: "CdC" };

/** Défauts de preuve : à corriger, jamais acquittables (même liste que le serveur). */
const HARD = new Set(["UNKNOWN_SOURCE", "FOREIGN_SOURCE", "FACT_WITHOUT_SOURCE", "UNKNOWN_FINDING", "INSTRUCTION_ECHO"]);

const errText = (e: unknown) => (e instanceof ApiError ? e.message : t.common.error);

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function DeliverableView({ id }: { id: string }) {
  const [d, setD] = useState<Deliverable | null>(null);
  const [role, setRole] = useState<Role>("consultant");
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [comments, setComments] = useState<CommentInfo[]>([]);
  const [edits, setEdits] = useState<Record<string, SectionDraft>>({});
  const [source, setSource] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draftComment, setDraftComment] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const [dd, vs, cs] = await Promise.all([
        deliverables.get(id),
        deliverables.versions(id),
        deliverables.comments(id),
      ]);
      setD(dd);
      setVersions(vs);
      setComments(cs);
      setEdits({});
    } catch (e) {
      setError(errText(e));
    }
  }, [id]);

  useEffect(() => {
    void load();
    deliverables.me().then((u) => setRole(u.role)).catch(() => {});
  }, [load]);

  const run = async (label: string, fn: () => Promise<string | void>) => {
    setBusy(label);
    setError(null);
    setMessage(null);
    try {
      const msg = await fn();
      if (msg) setMessage(msg);
      await load();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  };

  if (!d) return <p role={error ? "alert" : undefined}>{error ?? t.common.loading}</p>;

  const editable = d.state === "draft";
  const specs = d.sections?.length ? d.sections : (TEMPLATE_SECTIONS[d.type] ?? []).map((s) => ({ ...s, requires_labels: [] as string[] }));
  const byKey = new Map(d.content.sections.map((s) => [s.section_key, s]));
  const reportOf = (key: string) => d.reports.find((r) => r.report.section_key === key);

  const save = () =>
    run("save", async () => {
      const sections = d.content.sections.map((s) => edits[s.section_key] ?? s);
      const r = await deliverables.saveContent(id, { ...d.content, sections });
      return m.saved(r.version);
    });

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href={`/dossiers/${d.dossier_id}`}>{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
            <span>v{d.version}</span>
          </div>
          <h1>{TYPE_LABEL[d.type] ?? d.type.toUpperCase()}</h1>
          {(d.modules ?? []).length > 0 && (
            <div className="row" style={{ marginTop: 6 }} data-testid="modules">
              {(d.modules ?? []).map((k) => (
                <span key={k} className="tag">
                  {t.context.types[k] ?? k}
                </span>
              ))}
            </div>
          )}
        </div>
        {editable && (
          <div className="actions">
            <button className="btn btn-dark" disabled={busy !== null || Object.keys(edits).length === 0} onClick={save}>
              <Save size={16} />
              {m.save}
            </button>
          </div>
        )}
      </div>

      <div className="toolbar">
        <TransitionBar
          state={d.state}
          role={role}
          onTransition={(to, reason) => run("transition", () => deliverables.transition(id, to, reason).then(() => {}))}
        />
        <span className="sep" />
        <ExportBar
          state={d.state}
          onExport={(f: ExportFormat) =>
            run("export", async () => {
              const { blob, filename } = await deliverables.exportFile(id, f);
              download(blob, filename);
            })
          }
        />
      </div>
      {error && <Alert>{error}</Alert>}
      {message && (
        <div className="toast ok" role="status">
          <CheckCheck size={16} />
          {message}
        </div>
      )}

      <div className="split with-panel">
        <section>
          {specs.map(({ key, title: specTitle, requires_labels: needs }) => {
            const section = byKey.get(key);
            const report = reportOf(key);
            const hard = new Set(
              (report?.report.issues ?? []).filter((i) => HARD.has(i.code)).map((i) => i.sentence_index),
            );
            const failed = (report?.report.checks ?? []).filter((c) => c.status === "failed" && !hard.has(c.index));
            const ackItems = [
              ...failed.map((c) => ({ index: c.index, label: `${m.ack} #${c.index + 1}` })),
              ...(section?.status === "insufficient_evidence" ? [{ index: -1, label: m.ackRefusal }] : []),
            ];
            const sectionComments = comments.filter((c) => c.section_key === key);
            const title = sectionTitle(d.type, key) !== key ? sectionTitle(d.type, key) : specTitle;
            return (
              <article key={key} className="card section-card" data-testid={`section-${key}`}>
                <header>
                  <h2>{title}</h2>
                  {needs.length > 0 && (
                    <Link href={`/dossiers/${d.dossier_id}/decisions`} className="tag" title={m.needsDecisionHint}>
                      {m.needsDecision(needs.join(", "))}
                    </Link>
                  )}
                  {editable && (
                    <button
                      className="btn btn-primary btn-sm"
                      disabled={busy !== null}
                      onClick={() =>
                        run("gen-" + key, async () => {
                          await deliverables.generateSection(id, key);
                        })
                      }
                    >
                      <Sparkles size={14} />
                      {busy === "gen-" + key ? m.generating : m.generate}
                    </button>
                  )}
                  {editable && needs.length === 0 && section?.status === "insufficient_evidence" && (
                    <button
                      className="btn btn-sm"
                      title={m.proposeHint}
                      disabled={busy !== null}
                      data-testid={`propose-${key}`}
                      onClick={() =>
                        run("prop-" + key, async () => {
                          await deliverables.generateSection(id, key, true);
                        })
                      }
                    >
                      {busy === "prop-" + key ? m.generating : m.propose}
                    </button>
                  )}
                </header>
                {(busy === "gen-" + key || busy === "prop-" + key) && (
                  <WaitNote label={t.wait.section} typical={t.wait.sectionTypical} />
                )}
                <div className="section-body">
                  {section && (
                    <SectionEditor
                      section={section}
                      report={report}
                      editable={editable}
                      onChange={(s) => setEdits((e) => ({ ...e, [key]: s }))}
                      onSourceClick={setSource}
                    />
                  )}
                </div>
                {role !== "consultant" && d.state === "in_review" && ackItems.length > 0 && (
                  <div className="section-foot">
                    <AckBar
                      items={ackItems}
                      onAck={(index, reason) =>
                        run("ack", () => deliverables.acknowledge(id, key, index, reason).then(() => {}))
                      }
                    />
                  </div>
                )}
                <details className="comments" open={sectionComments.length > 0}>
                  <summary className="row" style={{ cursor: "pointer", gap: 6 }}>
                    <MessageSquare size={14} />
                    <h3>{m.comments}</h3>
                    {sectionComments.length > 0 && <span className="tag">{sectionComments.length}</span>}
                  </summary>
                  <ul>
                    {sectionComments.map((c) => (
                      <li key={c.id}>{c.text}</li>
                    ))}
                  </ul>
                  <div className="row">
                    <input
                      className="grow"
                      value={draftComment[key] ?? ""}
                      placeholder={m.commentPlaceholder}
                      aria-label={`${m.commentPlaceholder} ${title}`}
                      onChange={(e) => setDraftComment((c) => ({ ...c, [key]: e.target.value }))}
                    />
                    <button
                      className="btn btn-sm"
                      disabled={!(draftComment[key] ?? "").trim()}
                      onClick={() =>
                        run("comment", async () => {
                          await deliverables.addComment(id, key, draftComment[key]);
                          setDraftComment((c) => ({ ...c, [key]: "" }));
                        })
                      }
                    >
                      {m.addComment}
                    </button>
                  </div>
                </details>
              </article>
            );
          })}
          <VersionsPanel
            id={id}
            versions={versions}
            editable={editable}
            onRestore={(n) => run("restore", () => deliverables.restore(id, n).then(() => {}))}
            onError={(e) => setError(errText(e))}
          />
        </section>
        <SourcePanel chunkId={source} onClose={() => setSource(null)} />
      </div>
    </>
  );
}
