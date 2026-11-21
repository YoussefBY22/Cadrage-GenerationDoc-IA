"use client";

import { useCallback, useEffect, useState } from "react";
import SourcePanel from "@/components/SourcePanel";
import { ApiError } from "@/lib/api";
import { ExportBar, TransitionBar } from "./ActionBars";
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

const errText = (e: unknown) => (e instanceof ApiError ? e.message : "Une erreur est survenue");

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

  if (!d) return <p role={error ? "alert" : undefined}>{error ?? "Chargement…"}</p>;

  const editable = d.state === "draft";
  const specs = TEMPLATE_SECTIONS[d.type] ?? [];
  const byKey = new Map(d.content.sections.map((s) => [s.section_key, s]));
  const reportOf = (key: string) => d.reports.find((r) => r.report.section_key === key);

  const save = () =>
    run("save", async () => {
      const sections = d.content.sections.map((s) => edits[s.section_key] ?? s);
      const r = await deliverables.saveContent(id, { ...d.content, sections });
      return m.saved(r.version);
    });

  return (
    <div className="split">
      <section>
        <h1>{d.type.toUpperCase()}</h1>
        <TransitionBar
          state={d.state}
          role={role}
          onTransition={(to, reason) => run("transition", () => deliverables.transition(id, to, reason).then(() => {}))}
        />
        <ExportBar
          state={d.state}
          onExport={(f: ExportFormat) =>
            run("export", async () => {
              const { blob, filename } = await deliverables.exportFile(id, f);
              download(blob, filename);
            })
          }
        />
        {!editable && <p className="badge">{m.readonly}</p>}
        {error && <p role="alert">{error}</p>}
        {message && <p role="status">{message}</p>}

        {specs.map(({ key, title }) => {
          const section = byKey.get(key);
          const report = reportOf(key);
          const failed = report?.report.checks.filter((c) => c.status === "failed") ?? [];
          return (
            <article key={key} className="card" data-testid={`section-${key}`}>
              <h2>{title}</h2>
              {section && (
                <SectionEditor
                  section={section}
                  report={report}
                  editable={editable}
                  onChange={(s) => setEdits((e) => ({ ...e, [key]: s }))}
                  onSourceClick={setSource}
                />
              )}
              {editable && (
                <button disabled={busy !== null} onClick={() => run("gen-" + key, async () => {
                  await deliverables.generateSection(id, key);
                })}>
                  {busy === "gen-" + key ? m.generating : m.generate}
                </button>
              )}
              {role !== "consultant" &&
                failed.map((c) => (
                  <button
                    key={c.index}
                    onClick={() => run("ack", () => deliverables.acknowledge(id, key, c.index).then(() => {}))}
                  >
                    {m.ack} #{c.index + 1}
                  </button>
                ))}
              <h3>{m.comments}</h3>
              <ul>
                {comments
                  .filter((c) => c.section_key === key)
                  .map((c) => (
                    <li key={c.id}>{c.text}</li>
                  ))}
              </ul>
              <div className="row">
                <input
                  value={draftComment[key] ?? ""}
                  placeholder={m.commentPlaceholder}
                  aria-label={`${m.commentPlaceholder} ${title}`}
                  onChange={(e) => setDraftComment((c) => ({ ...c, [key]: e.target.value }))}
                />
                <button
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
            </article>
          );
        })}
        {editable && (
          <button disabled={busy !== null || Object.keys(edits).length === 0} onClick={save}>
            {m.save}
          </button>
        )}
        <VersionsPanel
          id={id}
          versions={versions}
          editable={editable}
          onRestore={(n) => run("restore", () => deliverables.restore(id, n).then(() => {}))}
          onError={(e) => setError(errText(e))}
        />
      </section>
      {source && <SourcePanel chunkId={source} onClose={() => setSource(null)} />}
    </div>
  );
}
