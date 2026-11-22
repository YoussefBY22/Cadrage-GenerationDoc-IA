"use client";

import { Check, ChevronRight, ListChecks, Pencil, Sparkles } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import SourcePanel from "@/components/SourcePanel";
import { Alert, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { Finding, Severity } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useGuard } from "@/lib/useGuard";

/** Liste des constats : valider, corriger le texte, ouvrir les sources dans le panneau de droite. */
export default function FindingsView({ dossierId }: { dossierId: string }) {
  const guard = useGuard();
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [source, setSource] = useState<{ chunk: string; finding: string } | null>(null);
  const [filter, setFilter] = useState<Severity | "all">("all");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api
      .listFindings(dossierId)
      .then(setFindings)
      .catch((e) => setError(guard(e)));
  }, [dossierId, guard]);

  useEffect(load, [load]);

  const patch = async (f: Finding, body: { text?: string; validated?: boolean }) => {
    setError(null);
    try {
      const updated = await api.patchFinding(f.id, body);
      setFindings((cur) => cur?.map((x) => (x.id === f.id ? updated : x)) ?? cur);
      setEditing(null);
    } catch (e) {
      setError(guard(e));
    }
  };

  const extract = async () => {
    setError(null);
    setBusy(true);
    try {
      await api.extractFindings(dossierId);
      load();
    } catch (e) {
      setError(guard(e));
    } finally {
      setBusy(false);
    }
  };

  const shown = findings?.filter((f) => filter === "all" || f.severity === filter) ?? [];
  const validated = findings?.filter((f) => f.validated).length ?? 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href={`/dossiers/${dossierId}`}>{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
          </div>
          <h1>{t.findings.title}</h1>
        </div>
        <div className="actions">
          {findings && findings.length > 0 && (
            <>
              <span className="badge approved plain">
                {validated}/{findings.length}
              </span>
              <div className="filter" role="group" aria-label={t.findings.title}>
                {(["all", "high", "medium", "low"] as const).map((s) => (
                  <button key={s} type="button" aria-pressed={filter === s} onClick={() => setFilter(s)}>
                    {s === "all" ? t.findings.all : t.findings.severity[s]}
                  </button>
                ))}
              </div>
            </>
          )}
          <button className="btn btn-primary" onClick={extract} disabled={busy}>
            <Sparkles size={16} />
            {t.findings.extract}
          </button>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}
      {findings === null && !error && <p className="muted">{t.common.loading}</p>}
      <div className={`split${source ? " with-panel" : ""}`}>
        <section>
          {findings?.length === 0 && <Empty icon={ListChecks} label={t.findings.none} />}
          <ul className="cards">
            {shown.map((f) => (
              <li
                key={f.id}
                className={`card finding sev-${f.severity}${source?.finding === f.id ? " selected" : ""}`}
                data-testid={`finding-${f.id}`}
              >
                <label style={{ display: "flex", alignItems: "flex-start", paddingTop: 2 }}>
                  <input
                    type="checkbox"
                    checked={f.validated}
                    onChange={(e) => patch(f, { validated: e.target.checked })}
                    aria-label={f.validated ? t.findings.unvalidate : t.findings.validate}
                  />
                </label>
                <div className="finding-body">
                  <div className="finding-meta">
                    <span className={`badge ${f.validated ? "approved" : "draft"}`}>
                      {f.validated ? t.findings.validated : t.findings.draft}
                    </span>
                    <span className={`badge sev-${f.severity}`}>{t.findings.severity[f.severity]}</span>
                    <span className="tag">{f.theme}</span>
                  </div>
                  {editing === f.id ? (
                    <>
                      <textarea
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        rows={4}
                        aria-label={t.findings.edit}
                        style={{ margin: "8px 0" }}
                      />
                      <div className="row">
                        <button className="btn btn-dark btn-sm" onClick={() => patch(f, { text: draft })}>
                          <Check size={14} />
                          {t.common.save}
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>
                          {t.common.cancel}
                        </button>
                      </div>
                    </>
                  ) : (
                    <p>{f.text}</p>
                  )}
                  <div className="row" style={{ gap: 6 }}>
                    {f.source_ids.map((sid, i) => (
                      <button key={sid} className="link" onClick={() => setSource({ chunk: sid, finding: f.id })}>
                        [{i + 1}]
                      </button>
                    ))}
                    {editing !== f.id && (
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ marginLeft: "auto" }}
                        onClick={() => {
                          setEditing(f.id);
                          setDraft(f.text);
                        }}
                      >
                        <Pencil size={13} />
                        {t.findings.edit}
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
        {source && <SourcePanel chunkId={source.chunk} onClose={() => setSource(null)} />}
      </div>
    </>
  );
}
