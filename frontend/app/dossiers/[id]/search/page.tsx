"use client";

import { ChevronRight, ExternalLink, FileText, LoaderCircle, Search, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Fragment, useEffect, useRef, useState } from "react";
import { clock } from "@/components/JobPanel";
import Shell from "@/components/Shell";
import SourcePanel from "@/components/SourcePanel";
import { Alert, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { SearchHit } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useDossier } from "@/lib/useDossier";
import { useGuard } from "@/lib/useGuard";
import { useViewerOpener } from "@/lib/viewerLink";

const WORDS_DELAY = 250; // mots exacts : dès qu'on s'arrête un instant de taper
const MEANING_DELAY = 900; // par le sens : après une vraie pause (appel au modèle de vecteurs)

/** Met en évidence les mots cherchés dans l'extrait, sans HTML injecté. */
function Marked({ text, query }: { text: string; query: string }) {
  const words = query
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter((w) => w.length > 2);
  if (!words.length) return <>{text}</>;
  const re = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return (
    <>
      {text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : <Fragment key={i}>{part}</Fragment>))}
    </>
  );
}

function snippet(text: string, query: string): string {
  const w = query.toLowerCase().split(/\s+/).find((x) => x.length > 2);
  const k = w ? text.toLowerCase().indexOf(w) : -1;
  const start = Math.max(0, k - 120);
  return (start > 0 ? "… " : "") + text.slice(start, start + 360) + (start + 360 < text.length ? " …" : "");
}

export default function SearchPage() {
  const { id } = useParams<{ id: string }>();
  const guard = useGuard();
  const dossier = useDossier(id);
  const viewer = useViewerOpener();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchHit[] | null>(null);
  const [mode, setMode] = useState<"words" | "meaning" | null>(null);
  const [pending, setPending] = useState<number | null>(null); // début de la recherche par le sens
  const [, setTick] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    const query = q.trim();
    const mine = ++seq.current;
    setError(null);
    if (query.length < 2) {
      setResults(null);
      setMode(null);
      setPending(null);
      return;
    }
    const w = window.setTimeout(() => {
      api
        .search(id, [query], 10, "words")
        .then((r) => {
          if (seq.current === mine) {
            setResults(r);
            setMode("words");
          }
        })
        .catch(() => {});
    }, WORDS_DELAY);
    const m = window.setTimeout(() => {
      setPending(Date.now());
      api
        .search(id, [query], 10, "meaning")
        .then((r) => {
          if (seq.current === mine) {
            setResults(r);
            setMode("meaning");
          }
        })
        .catch((e) => {
          if (seq.current === mine) setError(guard(e));
        })
        .finally(() => {
          if (seq.current === mine) setPending(null);
        });
    }, MEANING_DELAY);
    return () => {
      window.clearTimeout(w);
      window.clearTimeout(m);
    };
  }, [q, id, guard]);

  useEffect(() => {
    if (pending === null) return;
    const timer = window.setInterval(() => setTick((x) => x + 1), 500);
    return () => window.clearInterval(timer);
  }, [pending]);

  let status: string = t.search.howTo;
  if (pending !== null) status = t.search.meaningRunning(clock((Date.now() - pending) / 1000));
  else if (mode === "words") status = t.search.wordsShown;
  else if (mode === "meaning") status = t.search.meaningShown(results?.[0]?.elapsed_ms ?? 0);

  return (
    <Shell>
      {viewer.modal}
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href="/dossiers">{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
            <Link href={`/dossiers/${id}`}>{dossier?.name ?? "…"}</Link>
            <ChevronRight size={14} />
          </div>
          <h1>{t.search.title}</h1>
          <p className="page-hint">{t.search.hint}</p>
        </div>
      </div>
      <label className="search-bar search-live">
        <Search size={18} />
        <input
          type="search"
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t.search.placeholder}
          aria-label={t.search.placeholder}
        />
        {pending !== null && <LoaderCircle size={18} className="spin" aria-label={t.wait.search} />}
      </label>
      <p className="muted small search-status" aria-live="polite">
        {status}
      </p>
      {error && <Alert>{error}</Alert>}
      <div className={`split${source ? " with-panel" : ""}`}>
        <div>
          {results === null && <Empty icon={Search} label={t.search.empty} />}
          {results?.length === 0 && <Empty icon={Search} label={t.search.none} />}
          <ul className="cards">
            {results?.map((p) => (
              <li key={p.chunk.id} className="card">
                <div className="card-head">
                  <span className="small">
                    <FileText size={13} /> {p.filename ?? ""}
                    {p.chunk.page_start ? ` | ${t.findings.page} ${p.chunk.page_start}` : ""}
                  </span>
                  {p.chunk.injection_flags.length > 0 && (
                    <span className="badge warn plain">
                      <TriangleAlert size={13} />
                      {t.source.alert}
                    </span>
                  )}
                </div>
                <p style={{ margin: "0 0 10px" }}>
                  <Marked text={snippet(p.chunk.text, q)} query={q} />
                </p>
                <div className="row" style={{ gap: 12 }}>
                  <button className="link" onClick={() => setSource(p.chunk.id)}>
                    {t.search.showPassage}
                  </button>
                  <button className="link" onClick={() => void viewer.open({ docId: p.chunk.document_id, page: p.chunk.page_start })}>
                    <ExternalLink size={13} /> {t.findings.openInDoc}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
        {source && <SourcePanel chunkId={source} onClose={() => setSource(null)} />}
      </div>
    </Shell>
  );
}
