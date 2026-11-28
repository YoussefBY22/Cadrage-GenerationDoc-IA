"use client";

import { BookOpen, Check, ChevronRight, FileSpreadsheet, FileText, FileType2, Presentation, Trash2, TriangleAlert, Upload } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type DragEvent } from "react";
import JobPanel from "@/components/JobPanel";
import ProfileCard from "@/components/ProfileCard";
import WaitNote from "@/components/WaitNote";
import Shell from "@/components/Shell";
import { Alert, Empty } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { DeliverableSummary, DocumentInfo, DocumentRole, Dossier, Finding } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { getRefs, setRefs, type DossierRefs } from "@/lib/refs";
import { useGuard } from "@/lib/useGuard";
import { useJob } from "@/lib/useJob";

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

const OTHER_ROLES: DocumentRole[] = ["other", "strategy", "portfolio", "template"];
const ALL_ROLES: DocumentRole[] = ["diagnostic", ...OTHER_ROLES];

function DocTable({
  docs,
  alerts,
  onRole,
  onDelete,
}: {
  docs: DocumentInfo[];
  alerts: Record<string, number>;
  onRole: (d: DocumentInfo, r: DocumentRole) => void;
  onDelete: (d: DocumentInfo) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{t.dossier.file}</th>
            <th>{t.coeur.role}</th>
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
              <td>
                <select
                  className="mini-select"
                  value={d.role}
                  aria-label={`${t.coeur.role} : ${d.title || d.filename}`}
                  onChange={(e) => onRole(d, e.target.value as DocumentRole)}
                >
                  {ALL_ROLES.map((r) => (
                    <option key={r} value={r}>
                      {t.coeur.roles[r]}
                    </option>
                  ))}
                </select>
                {d.role === "template" && <small className="muted"> {t.coeur.templateNote}</small>}
              </td>
              <td className="num">{d.pages ?? "–"}</td>
              <td className="actions">
                {(alerts[d.id] ?? 0) > 0 && (
                  <span className="badge warn plain">
                    <TriangleAlert size={13} />
                    {t.alerts(alerts[d.id])}
                  </span>
                )}
                <a className="btn btn-sm" href={`/documents/${d.id}`} target="cadrage-document" rel="noopener" data-testid={`read-${d.id}`}>
                  <BookOpen size={14} />
                  {t.dossier.read}
                </a>
                <button type="button" className="btn btn-ghost btn-sm danger" onClick={() => onDelete(d)} data-testid={`delete-${d.id}`}>
                  <Trash2 size={14} />
                  {t.common.delete}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Drop({
  label,
  testid,
  busy,
  compact,
  onFiles,
}: {
  label: string;
  testid: string;
  busy: boolean;
  compact: boolean;
  onFiles: (files: FileList | File[]) => void;
}) {
  const [over, setOver] = useState(false);
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
  };
  return (
    <label
      className={`drop${over ? " over" : ""}${compact ? " compact" : ""}`}
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
      {busy ? t.dossier.uploading : label}
      <small>{t.dossier.dropFormats}</small>
      {busy && <WaitNote label={t.wait.upload} typical={t.wait.uploadTypical} />}
      <input
        type="file"
        multiple
        hidden
        data-testid={testid}
        accept=".pdf,.docx,.pptx,.txt,.md"
        onChange={(e) => {
          if (e.target.files) onFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </label>
  );
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
  const [importRole, setImportRole] = useState<DocumentRole>("other");
  const [recoAlerts, setRecoAlerts] = useState(0);
  const [deliverables, setDeliverables] = useState<DeliverableSummary[]>([]);

  const reload = useCallback(() => {
    api
      .listDocuments(id)
      .then(setDocs)
      .catch((e) => setError(guard(e)));
    api
      .listFindings(id)
      .then(setFindings)
      .catch(() => {});
    api
      .listRecommendations(id)
      .then((r) => setRecoAlerts(r.alerts))
      .catch(() => {});
    api
      .listDeliverables(id)
      .then((list) => {
        setDeliverables(list);
        const latest = (type: string) => list.find((d) => d.type === type)?.id;
        setRefsState((cur) => ({ ...cur, roadmap: latest("roadmap"), tor: latest("tor"), cdc: latest("cdc") }));
      })
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

  const upload = async (files: FileList | File[], role: DocumentRole) => {
    setBusy("upload");
    setMessages([]);
    for (const file of Array.from(files)) {
      try {
        const r = await api.uploadDocument(id, file, role);
        setAlerts((a) => ({ ...a, [r.document_id]: r.alerts }));
        setMessages((m) => [...m, t.dossier.imported(file.name, r.chunks)]);
      } catch (e) {
        setMessages((m) => [...m, `${file.name} : ${uploadMessage(e, guard)}`]);
      }
    }
    setBusy(null);
    reload();
  };

  const changeRole = async (d: DocumentInfo, role: DocumentRole) => {
    try {
      const updated = await api.setDocumentRole(d.id, role);
      setDocs((cur) => cur?.map((x) => (x.id === d.id ? { ...x, role: updated.role } : x)) ?? cur);
    } catch (e) {
      setError(guard(e));
    }
  };

  const validated = findings.filter((f) => f.validated).length;

  const deleteDocument = async (d: DocumentInfo) => {
    try {
      const p = await api.documentDeletePreview(d.id);
      if (!window.confirm(t.dossier.confirmDeleteDocument(d.title || d.filename, p))) return;
      await api.deleteDocument(d.id);
      reload();
    } catch (e) {
      setError(guard(e));
    }
  };

  const deleteDossier = async () => {
    try {
      const p = await api.dossierDeletePreview(id);
      if (!window.confirm(t.dossier.confirmDeleteDossier(dossier?.name ?? "", p))) return;
      await api.deleteDossier(id);
      router.push("/dossiers");
    } catch (e) {
      setError(guard(e));
    }
  };

  const deleteDeliverable = async (d: DeliverableSummary) => {
    if (!window.confirm(t.dossier.confirmDeleteDeliverable(t.dossier.deliverableType[d.type]))) return;
    try {
      await api.deleteDeliverable(d.id);
      reload();
    } catch (e) {
      setError(guard(e));
    }
  };

  const roadmapJob = useJob(id, "roadmap", (j) => {
    const did = j.result?.deliverable_id as string | undefined;
    if (j.status === "done" && did) {
      const items = (j.result?.roadmap as { items?: { rank: number; initiative: { id: string } }[] } | undefined)?.items ?? [];
      const top = [...items].sort((a, b) => a.rank - b.rank)[0];
      setRefsState(setRefs(id, { roadmap: did, initiative: top?.initiative.id }));
      router.push(`/deliverables/${did}/roadmap`);
    }
  });

  const roadmap = async () => {
    if (refs.roadmap) return router.push(`/deliverables/${refs.roadmap}/roadmap`);
    setError(null);
    await roadmapJob.start();
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
  const diagnostics = (docs ?? []).filter((d) => d.role === "diagnostic");
  const others = (docs ?? []).filter((d) => d.role !== "diagnostic");
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
          <button type="button" className="btn btn-ghost danger" onClick={deleteDossier} data-testid="delete-dossier">
            <Trash2 size={16} />
            {t.dossier.deleteDossier}
          </button>
        </div>
      </div>
      <p className="page-hint" style={{ marginTop: -8, marginBottom: 16 }}>{t.dossier.hint}</p>
      {recoAlerts > 0 && (
        <Alert>
          <Link href={`/dossiers/${id}/recommendations`}>{t.projet.alertsBanner(recoAlerts)}</Link>
        </Alert>
      )}
      {error && <Alert>{error}</Alert>}

      <ProfileCard dossierId={id} />
      {roadmapJob.error && <Alert>{roadmapJob.error}</Alert>}
      {roadmapJob.job && (
        <JobPanel job={roadmapJob.job} onCancel={() => void roadmapJob.cancel()} onClose={roadmapJob.dismiss} />
      )}

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
        <div>
          <h2>{t.coeur.diagnostics}</h2>
          <small className="muted">{t.coeur.diagnosticsHint}</small>
        </div>
      </div>
      <Drop
        label={t.coeur.diagnosticsDrop}
        testid="diagnostic-input"
        busy={busy === "upload"}
        compact={diagnostics.length > 0}
        onFiles={(f) => void upload(f, "diagnostic")}
      />
      <div style={{ marginTop: 14 }}>
        {docs && diagnostics.length === 0 ? (
          <Empty icon={FileText} label={t.coeur.noDiagnostics} flat />
        ) : (
          docs && <DocTable docs={diagnostics} alerts={alerts} onRole={changeRole} onDelete={(d) => void deleteDocument(d)} />
        )}
      </div>

      <div className="section-title" style={{ marginTop: 28 }}>
        <h2>{t.coeur.others}</h2>
        <label className="row" style={{ gap: 8 }}>
          <span className="muted">{t.coeur.importAs}</span>
          <select
            className="mini-select"
            value={importRole}
            aria-label={t.coeur.importAs}
            onChange={(e) => setImportRole(e.target.value as DocumentRole)}
          >
            {OTHER_ROLES.map((r) => (
              <option key={r} value={r}>
                {t.coeur.roles[r]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Drop
        label={t.dossier.dropHere}
        testid="file-input"
        busy={busy === "upload"}
        compact={others.length > 0}
        onFiles={(f) => void upload(f, importRole)}
      />
      {messages.length > 0 && (
        <ul className="muted" style={{ listStyle: "none", padding: 0, margin: "10px 0 0" }}>
          {messages.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ul>
      )}
      <div style={{ marginTop: 14 }}>
        {docs && others.length === 0 ? (
          <Empty icon={FileText} label={t.dossier.noDocuments} flat />
        ) : (
          docs && <DocTable docs={others} alerts={alerts} onRole={changeRole} onDelete={(d) => void deleteDocument(d)} />
        )}
      </div>

      <div className="section-title" style={{ marginTop: 28 }}>
        <div>
          <h2>{t.dossier.deliverables}</h2>
          <small className="muted">{t.dossier.deliverablesHint}</small>
        </div>
      </div>
      {deliverables.length === 0 ? (
        <Empty icon={FileText} label={t.dossier.noDeliverables} flat />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t.dossier.deliverableCol}</th>
                <th>{t.dossier.updated}</th>
                <th>{t.dossier.versionCol}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {deliverables.map((d) => (
                <tr key={d.id}>
                  <td>
                    <Link href={d.type === "roadmap" ? `/deliverables/${d.id}/roadmap` : `/deliverables/${d.id}`}>
                      {t.dossier.deliverableType[d.type]}
                    </Link>
                  </td>
                  <td>{d.updated_at ? new Date(d.updated_at).toLocaleString() : "–"}</td>
                  <td className="num">{d.version}</td>
                  <td className="actions">
                    <button type="button" className="btn btn-ghost btn-sm danger" onClick={() => void deleteDeliverable(d)}>
                      <Trash2 size={14} />
                      {t.common.delete}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Shell>
  );
}
