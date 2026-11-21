"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type DragEvent } from "react";
import Shell from "@/components/Shell";
import { ApiError, api } from "@/lib/api";
import type { DocumentInfo, Dossier } from "@/lib/api-types";
import { t } from "@/lib/i18n/fr";
import { useGuard } from "@/lib/useGuard";

function uploadMessage(err: unknown, guard: (e: unknown) => string): string {
  if (err instanceof ApiError) {
    if (err.status === 409) return t.dossier.duplicate;
    if (err.status === 413) return t.dossier.tooLarge;
    if (err.status === 415) return t.dossier.unsupported;
  }
  return guard(err);
}

export default function DossierPage() {
  const { id } = useParams<{ id: string }>();
  const guard = useGuard();
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [alerts, setAlerts] = useState<Record<string, number>>({});
  const [messages, setMessages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);

  const reload = useCallback(() => {
    api
      .listDocuments(id)
      .then(setDocs)
      .catch((e) => setError(guard(e)));
  }, [id, guard]);

  useEffect(() => {
    api
      .getDossier(id)
      .then(setDossier)
      .catch((e) => setError(guard(e)));
    reload();
  }, [id, guard, reload]);

  const upload = async (files: FileList | File[]) => {
    setBusy(true);
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
    setBusy(false);
    reload();
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    if (e.dataTransfer.files.length) void upload(e.dataTransfer.files);
  };

  return (
    <Shell>
      <h1>{dossier ? `${dossier.name} — ${dossier.client_name}` : t.common.loading}</h1>
      <nav className="row">
        <Link href={`/dossiers/${id}/search`}>{t.dossier.search}</Link>
        <Link href={`/dossiers/${id}/findings`}>{t.dossier.findings}</Link>
      </nav>
      {error && <p role="alert">{error}</p>}
      <h2>{t.dossier.documents}</h2>
      <label
        className={`drop${over ? " over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        style={{ display: "block" }}
      >
        {busy ? t.dossier.uploading : t.dossier.dropHere}
        <input
          type="file"
          multiple
          hidden
          accept=".pdf,.docx,.pptx,.txt,.md"
          onChange={(e) => e.target.files && void upload(e.target.files)}
        />
      </label>
      <ul>
        {messages.map((m, i) => (
          <li key={i}>{m}</li>
        ))}
      </ul>
      {docs.length === 0 && <p>{t.dossier.noDocuments}</p>}
      <ul className="cards">
        {docs.map((d) => (
          <li key={d.id} className="card">
            {d.title || d.filename}
            {d.pages != null && ` — ${d.pages} ${t.dossier.pages}`}{" "}
            {(alerts[d.id] ?? 0) > 0 && <span className="badge warn">⚠ {t.alerts(alerts[d.id])}</span>}
          </li>
        ))}
      </ul>
    </Shell>
  );
}
