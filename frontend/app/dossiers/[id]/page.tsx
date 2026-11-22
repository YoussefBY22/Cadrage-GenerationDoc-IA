"use client";

import { Check, ChevronRight, FileSpreadsheet, FileText, FileType2, Presentation, Search, TriangleAlert, Upload } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type DragEvent } from "react";
import Shell from "@/components/Shell";
import { Alert, Empty } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { DocumentInfo, Dossier, Finding } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { getRefs, setRefs, type DossierRefs } from "@/lib/refs";
import { useGuard } from "@/lib/useGuard";

function uploadMessage(err: unknown, guard: (e: unknown) => string): string {
  if (err instanceof ApiError) {
    if (err.status === 409) return t.dossier.duplicate;
    if (err.status === 413) return t.dossier.tooLarge;
    if (err.status === 415) return t.dossier.unsupported;
  }
  return guard(err);
}

function DocIcon({ name }: { name: string }) {
  const ext = name.split(".").pop()?.toLowerCase();
  const Icon = ext === "pptx" ? Presentation : ext === "docx" ? FileType2 : ext === "pdf" ? FileSpreadsheet : FileText;
  return <Icon size={18} className="doc-ico" />;
}

export default function DossierPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const guard = useGuard();
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [docs, setDocs] = useState<DocumentInfo[] | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [refs, setRefsState] = useState<DossierRefs>({});
  const [alerts, setAlerts] = useState<Record<string, number>>({});
  const [messages, setMessages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [over, setOver] = useState(false);

  const reload = useCallback(() => {
    api
      .listDocuments(id)
      .then(setDocs)
      .catch((e) => setError(guard(e)));
    api
      .listFindings(id)
      .then(setFindings)
      .catch(() => {});
  }, [id, guard]);

  useEffect(() => {
    api
      .getDossier(id)
      .then(setDossier)
      .catch((e) => setError(guard(e)));
    setRefsState(getRefs(id));
    reload();
  }, [id, guard, reload]);

  const upload = async (files: FileList | File[]) => {
    setBusy("upload");
    setMessages([]);
    for (const file of Array.from(files)) {
      try {
        const r = await api.uploadDocument(id, file);
        setAlerts((a) => ({ ...a, [r.document_id]: r.alerts }));
        setMessages((m) => [...m, t.dossier.imported(file.name, r.chunks)]);
      } catch (e) {
        setMessages((m) => [...m, `${file.name} : ${uploadMessage(e, guard)}`]);
      }
    }
    setBusy(null);
    reload();
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    if (e.dataTransfer.files.length) void upload(e.dataTransfer.files);
  };

  const validated = findings.filter((f) => f.validated).length;

  const roadmap = async () => {
    if (refs.roadmap) return router.push(`/deliverables/${refs.roadmap}/roadmap`);
    setBusy("roadmap");
    setError(null);
    try {
      const r = await api.generateRoadmap(id);
      const top = [...r.roadmap.items].sort((a, b) => a.rank - b.rank)[0];
      setRefsState(setRefs(id, { roadmap: r.deliverable_id, initiative: top?.initiative.id }));
      router.push(`/deliverables/${r.deliverable_id}/roadmap`);
    } catch (e) {
      setError(guard(e));
    } finally {
      setBusy(null);
    }
  };

  const tor = async () => {
    if (refs.tor) return router.push(`/deliverables/${refs.tor}`);
    setBusy("tor");
    setError(null);
    try {
      const r = await api.createDeliverable(id, "tor", refs.initiative);
      setRefsState(setRefs(id, { tor: r.deliverable_id }));
      router.push(`/deliverables/${r.deliverable_id}`);
    } catch (e) {
      setError(guard(e));
    } finally {
      setBusy(null);
    }
  };

  const hasDocs = (docs?.length ?? 0) > 0;
  const steps = [
    { key: "documents", label: t.dossier.steps.documents, sub: `${docs?.length ?? 0}`, done: hasDocs, run: () => document.getElementById("documents")?.scrollIntoView({ behavior: "smooth" }), off: false },
    { key: "findings", label: t.dossier.steps.findings, sub: `${validated}/${findings.length}`, done: validated > 0, run: () => router.push(`/dossiers/${id}/findings`), off: !hasDocs },
    { key: "roadmap", label: t.dossier.steps.roadmap, sub: refs.roadmap ? t.common.open : "", done: !!refs.roadmap, run: roadmap, off: validated === 0 && !refs.roadmap },
    { key: "tor", label: t.dossier.steps.tor, sub: refs.tor ? t.common.open : "", done: !!refs.tor, run: tor, off: validated === 0 && !refs.tor },
  ];
  const current = steps.findIndex((s) => !s.done);

  return (
    <Shell>
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href="/dossiers">{t.nav.dashboard}</Link>
            <ChevronRight size={14} />
            <span>{dossier?.client_name ?? "…"}</span>
          </div>
          <h1>{dossier ? dossier.name : t.common.loading}</h1>
        </div>
        <div className="actions">
          <Link href={`/dossiers/${id}/search`} className="btn">
            <Search size={16} />
            {t.dossier.search}
          </Link>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}

      <div className="steps">
        {steps.map((s, i) => (
          <button
            key={s.key}
            type="button"
            className={`step${s.done ? " done" : ""}${i === current ? " current" : ""}`}
            onClick={s.run}
            disabled={s.off || busy === s.key}
            data-testid={`step-${s.key}`}
          >
            <span className="step-dot">{s.done ? <Check size={14} strokeWidth={3} /> : i + 1}</span>
            <span style={{ minWidth: 0 }}>
              <b>{s.label}</b>
              <small>{busy === s.key ? t.common.loading : s.sub || " "}</small>
            </span>
          </button>
        ))}
      </div>

      <div className="section-title" id="documents">
        <h2>{t.dossier.documents}</h2>
      </div>
      <label
        className={`drop${over ? " over" : ""}${hasDocs ? " compact" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <span className="drop-ico">
          <Upload size={20} />
        </span>
        {busy === "upload" ? t.dossier.uploading : t.dossier.dropHere}
        <small>{t.dossier.dropFormats}</small>
        <input
          type="file"
          multiple
          hidden
          data-testid="file-input"
          accept=".pdf,.docx,.pptx,.txt,.md"
          onChange={(e) => e.target.files && void upload(e.target.files)}
        />
      </label>
      {messages.length > 0 && (
        <ul className="muted" style={{ listStyle: "none", padding: 0, margin: "10px 0 0" }}>
          {messages.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ul>
      )}

      <div style={{ marginTop: 20 }}>
        {docs?.length === 0 ? (
          <Empty icon={FileText} label={t.dossier.noDocuments} />
        ) : (
          docs && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t.dossier.file}</th>
                    <th>{t.dossier.pages}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <span className="doc-name">
                          <DocIcon name={d.filename} />
                          {d.title || d.filename}
                        </span>
                      </td>
                      <td className="num">{d.pages ?? "–"}</td>
                      <td className="num">
                        {(alerts[d.id] ?? 0) > 0 && (
                          <span className="badge warn plain">
                            <TriangleAlert size={13} />
                            {t.alerts(alerts[d.id])}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    </Shell>
  );
}
