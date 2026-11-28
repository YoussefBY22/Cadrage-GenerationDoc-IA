"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import EvidenceViewer from "@/components/EvidenceViewer";

/** Lecture d'un document avec ses preuves surlignées (constats, recommandations), sans téléchargement. */
function Page() {
  const { docId } = useParams<{ docId: string }>();
  const q = useSearchParams();
  return (
    <EvidenceViewer
      key={docId}
      docId={docId}
      page={Number(q.get("page") ?? 1) || 1}
      findingId={q.get("finding")}
      recoId={q.get("reco")}
    />
  );
}

export default function DocumentPage() {
  return (
    <Suspense>
      <Page />
    </Suspense>
  );
}
