"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ChunkDetail } from "@/lib/api-types";
import { t } from "@/lib/i18n/fr";
import { useGuard } from "@/lib/useGuard";

/** Panneau latéral : texte brut du passage cité (jamais de HTML injecté). */
export default function SourcePanel({
  chunkId,
  onClose,
}: {
  chunkId: string;
  onClose: () => void;
}) {
  const guard = useGuard();
  const [chunk, setChunk] = useState<ChunkDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setChunk(null);
    setError(null);
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
        <h2>{t.source.title}</h2>
        <button onClick={onClose}>{t.common.close}</button>
      </header>
      {error && <p role="alert">{error}</p>}
      {!chunk && !error && <p>{t.common.loading}</p>}
      {chunk && (
        <>
          <p>
            <strong>{chunk.document}</strong>
            {chunk.page_start != null && (
              <>
                {" "}
                — {t.source.page} {chunk.page_start}
                {chunk.page_end != null && chunk.page_end !== chunk.page_start
                  ? `–${chunk.page_end}`
                  : ""}
              </>
            )}
          </p>
          {chunk.section_path.length > 0 && (
            <p>
              {t.source.section} : {chunk.section_path.join(" › ")}
            </p>
          )}
          {chunk.injection_flags.length > 0 && (
            <p className="badge warn" role="note">
              ⚠ {t.source.alert} :{" "}
              {chunk.injection_flags.map((f) => t.source.flags[f] ?? f).join(", ")}
            </p>
          )}
          <pre className="passage">{chunk.text}</pre>
        </>
      )}
    </aside>
  );
}
