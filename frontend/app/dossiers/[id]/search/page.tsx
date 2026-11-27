"use client";

import { ChevronRight, Search, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import Shell from "@/components/Shell";
import SourcePanel from "@/components/SourcePanel";
import { Alert, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { Passage } from "@/lib/api-types";
import { t } from "@/lib/i18n";
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
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href={`/dossiers/${id}`}>{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
          </div>
          <h1>{t.search.title}</h1>
          <p className="page-hint">{t.search.hint}</p>
        </div>
      </div>
      <form onSubmit={submit} className="search-bar">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t.search.placeholder}
          aria-label={t.search.placeholder}
        />
        <button type="submit" className="btn btn-primary">
          <Search size={16} />
          {t.search.submit}
        </button>
      </form>
      {error && <Alert>{error}</Alert>}
      <div className={`split${source ? " with-panel" : ""}`}>
        <div>
          {results === null && <Empty icon={Search} label={t.search.placeholder} />}
          {results?.length === 0 && <Empty icon={Search} label={t.search.none} />}
          <ul className="cards">
            {results?.map((p) => (
              <li key={p.chunk.id} className="card">
                <div className="card-head">
                  <strong>{p.label}</strong>
                  {p.chunk.injection_flags.length > 0 && (
                    <span className="badge warn plain">
                      <TriangleAlert size={13} />
                      {t.source.alert}
                    </span>
                  )}
                </div>
                <p style={{ margin: "0 0 10px" }}>{p.chunk.text.slice(0, 300)}</p>
                <button className="link" onClick={() => setSource(p.chunk.id)}>
                  {t.source.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
        {source && <SourcePanel chunkId={source} onClose={() => setSource(null)} />}
      </div>
    </Shell>
  );
}
