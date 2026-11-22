"use client";

import { BookOpen, FileText, TriangleAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { ChunkDetail } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useGuard } from "@/lib/useGuard";

/** Panneau latéral : texte brut du passage cité (jamais de HTML injecté). */
export default function SourcePanel({
  chunkId,
  onClose,
}: {
  chunkId: string | null;
  onClose: () => void;
}) {
  const guard = useGuard();
  const [chunk, setChunk] = useState<ChunkDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setChunk(null);
    setError(null);
    if (!chunkId) return;
    api
      .getChunk(chunkId)
      .then((c) => alive && setChunk(c))
      .catch((e) => alive && setError(guard(e)));
    return () => {
      alive = false;
    };
  }, [chunkId, guard]);

  return (
    <aside className="panel" role="complementary" aria-label={t.source.title}>
      <header>
        <h2>
          <BookOpen size={16} />
          {t.source.title}
        </h2>
        <button className="btn btn-ghost btn-icon" onClick={onClose} aria-label={t.common.close}>
          <X size={16} />
        </button>
      </header>
      <div className="panel-body">
        {error && <p role="alert">{error}</p>}
        {!chunkId && <Empty icon={BookOpen} label={t.source.empty} flat />}
        {chunkId && !chunk && !error && <p className="panel-empty">{t.common.loading}</p>}
        {chunk && (
          <>
            <div className="src-doc">
              <FileText size={16} />
              {chunk.document}
            </div>
            <div className="src-meta">
              {chunk.page_start != null && (
                <span className="tag">
                  {t.source.page} {chunk.page_start}
                  {chunk.page_end != null && chunk.page_end !== chunk.page_start ? `–${chunk.page_end}` : ""}
                </span>
              )}
              {chunk.section_path.length > 0 && <span>{chunk.section_path.join(" › ")}</span>}
            </div>
            {chunk.injection_flags.length > 0 && (
              <p className="badge warn plain" role="note" style={{ borderRadius: 4, marginTop: 0 }}>
                <TriangleAlert size={14} />
                {t.source.alert} : {chunk.injection_flags.map((f) => t.source.flags[f] ?? f).join(", ")}
              </p>
            )}
            <pre className="passage">{chunk.text}</pre>
          </>
        )}
      </div>
    </aside>
  );
}
