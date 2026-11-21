"use client";

import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import Shell from "@/components/Shell";
import SourcePanel from "@/components/SourcePanel";
import { api } from "@/lib/api";
import type { Passage } from "@/lib/api-types";
import { t } from "@/lib/i18n/fr";
import { useGuard } from "@/lib/useGuard";

export default function SearchPage() {
  const { id } = useParams<{ id: string }>();
  const guard = useGuard();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Passage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      setResults(await api.search(id, [q]));
    } catch (err) {
      setError(guard(err));
    }
  };

  return (
    <Shell>
      <h1>{t.search.title}</h1>
      <form onSubmit={submit} className="row">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t.search.placeholder}
          aria-label={t.search.placeholder}
          style={{ flex: 1 }}
        />
        <button type="submit">{t.search.submit}</button>
      </form>
      {error && <p role="alert">{error}</p>}
      <div className="split">
        <ul className="cards">
          {results?.length === 0 && <li>{t.search.none}</li>}
          {results?.map((p) => (
            <li key={p.chunk.id} className="card">
              <strong>{p.label}</strong>
              {p.chunk.injection_flags.length > 0 && (
                <span className="badge warn"> ⚠ {t.source.alert}</span>
              )}
              <p>{p.chunk.text.slice(0, 300)}</p>
              <button className="link" onClick={() => setSource(p.chunk.id)}>
                {t.source.title}
              </button>
            </li>
          ))}
        </ul>
        {source && <SourcePanel chunkId={source} onClose={() => setSource(null)} />}
      </div>
    </Shell>
  );
}
