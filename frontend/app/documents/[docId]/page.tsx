"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Alert } from "@/components/ui";
import { api } from "@/lib/api";
import type { DocumentInfo, Finding } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useGuard } from "@/lib/useGuard";

/** Lecture d'un document dans le navigateur, sans téléchargement, ouvert à la page demandée. */
function Viewer() {
  const { docId } = useParams<{ docId: string }>();
  const q = useSearchParams();
  const page = q.get("page") ?? "1";
  const findingId = q.get("finding");
  const guard = useGuard();
  const [doc, setDoc] = useState<DocumentInfo | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let created: string | null = null;
    api
      .getDocument(docId)
      .then((d) => {
        setDoc(d);
        document.title = d.title || d.filename;
        if (findingId)
          api
            .listFindings(d.dossier_id)
            .then((all) => setFinding(all.find((f) => f.id === findingId) ?? null))
            .catch(() => {});
      })
      .catch((e) => setError(guard(e)));
    api
      .documentFile(docId)
      .then((b) => {
        created = URL.createObjectURL(b);
        setUrl(created);
      })
      .catch((e) => setError(guard(e)));
    return () => {
      if (created) URL.revokeObjectURL(created);
    };
  }, [docId, findingId, guard]);

  return (
    <div className="viewer">
      <header className="viewer-head">
        {doc && (
          <Link href={`/dossiers/${doc.dossier_id}`} className="btn btn-ghost btn-sm">
            <ArrowLeft size={14} />
            {t.nav.back}
          </Link>
        )}
        <div style={{ minWidth: 0 }}>
          <b>{doc ? doc.title || doc.filename : t.common.loading}</b>
          <small className="muted">
            {" "}
            · {t.findings.page} {page}
            {doc?.pages ? ` / ${doc.pages}` : ""}
          </small>
        </div>
      </header>
      {finding && (
        <div className="viewer-finding">
          <small className="muted">{t.viewer.finding}</small>
          <p>{finding.text}</p>
        </div>
      )}
      {error && <Alert>{error}</Alert>}
      {url && <iframe className="viewer-frame" src={`${url}#page=${page}`} title={doc?.filename ?? "document"} />}
    </div>
  );
}

export default function DocumentPage() {
  return (
    <Suspense>
      <Viewer />
    </Suspense>
  );
}
