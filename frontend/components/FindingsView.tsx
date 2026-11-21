"use client";

import { useCallback, useEffect, useState } from "react";
import SourcePanel from "@/components/SourcePanel";
import { api } from "@/lib/api";
import type { Finding } from "@/lib/api-types";
import { t } from "@/lib/i18n/fr";
import { useGuard } from "@/lib/useGuard";

/** Liste des constats : cocher (valider), corriger le texte, ouvrir les sources. */
export default function FindingsView({ dossierId }: { dossierId: string }) {
  const guard = useGuard();
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [source, setSource] = useState<string | null>(null);

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
    try {
      await api.extractFindings(dossierId);
      load();
    } catch (e) {
      setError(guard(e));
    }
  };

  return (
    <div className="split">
      <section>
        <div className="row">
          <h1>{t.findings.title}</h1>
          <button onClick={extract}>{t.findings.extract}</button>
        </div>
        {error && <p role="alert">{error}</p>}
        {findings === null && !error && <p>{t.common.loading}</p>}
        {findings?.length === 0 && <p>{t.findings.none}</p>}
        <ul className="cards">
          {findings?.map((f) => (
            <li key={f.id} className="card" data-testid={`finding-${f.id}`}>
              <div className="row">
                <label>
                  <input
                    type="checkbox"
                    checked={f.validated}
                    onChange={(e) => patch(f, { validated: e.target.checked })}
                    aria-label={f.validated ? t.findings.unvalidate : t.findings.validate}
                  />{" "}
                  {f.validated ? t.findings.validated : t.findings.draft}
                </label>
                <span className={`badge sev-${f.severity}`}>{t.findings.severity[f.severity]}</span>
                <span className="badge">{f.theme}</span>
              </div>
              {editing === f.id ? (
                <>
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    rows={4}
                    aria-label={t.findings.edit}
                  />
                  <button onClick={() => patch(f, { text: draft })}>{t.common.save}</button>{" "}
                  <button onClick={() => setEditing(null)}>{t.common.cancel}</button>
                </>
              ) : (
                <p>
                  {f.text}{" "}
                  <button
                    onClick={() => {
                      setEditing(f.id);
                      setDraft(f.text);
                    }}
                  >
                    {t.findings.edit}
                  </button>
                </p>
              )}
              <p>
                {t.findings.sources} :{" "}
                {f.source_ids.map((id, i) => (
                  <button key={id} className="link" onClick={() => setSource(id)}>
                    [{i + 1}]
                  </button>
                ))}
              </p>
            </li>
          ))}
        </ul>
      </section>
      {source && <SourcePanel chunkId={source} onClose={() => setSource(null)} />}
    </div>
  );
}
