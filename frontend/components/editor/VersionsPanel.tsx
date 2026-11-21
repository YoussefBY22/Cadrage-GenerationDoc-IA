"use client";

import { useState } from "react";
import { deliverables } from "./client";
import { m } from "./i18n";
import type { SectionDiff, VersionInfo } from "./types";

/** Liste des versions, restauration (si éditable) et comparaison de deux versions. */
export default function VersionsPanel({
  id,
  versions,
  editable,
  onRestore,
  onError,
}: {
  id: string;
  versions: VersionInfo[];
  editable: boolean;
  onRestore: (n: number) => void;
  onError: (e: unknown) => void;
}) {
  const last = versions.at(-1)?.version ?? 1;
  const [from, setFrom] = useState(Math.max(1, last - 1));
  const [to, setTo] = useState(last);
  const [diff, setDiff] = useState<SectionDiff[] | null>(null);

  const compare = async () => {
    try {
      setDiff((await deliverables.diff(id, from, to)).sections);
    } catch (e) {
      onError(e);
    }
  };

  const options = versions.map((v) => (
    <option key={v.version} value={v.version}>
      v{v.version}
    </option>
  ));

  return (
    <section>
      <h2>{m.versions}</h2>
      <ul>
        {versions.map((v) => (
          <li key={v.version}>
            v{v.version} — {v.origin} {v.created_at ?? ""}{" "}
            {editable && v.version !== last && (
              <button onClick={() => onRestore(v.version)}>{m.restore}</button>
            )}
          </li>
        ))}
      </ul>
      <div className="row">
        <label>
          {m.from}{" "}
          <select value={from} onChange={(e) => setFrom(Number(e.target.value))}>
            {options}
          </select>
        </label>
        <label>
          {m.to}{" "}
          <select value={to} onChange={(e) => setTo(Number(e.target.value))}>
            {options}
          </select>
        </label>
        <button onClick={compare}>{m.compare}</button>
      </div>
      {diff && (
        <div data-testid="diff">
          {diff.every((s) => s.status === "unchanged") && <p>{m.diffNone}</p>}
          {diff
            .filter((s) => s.status !== "unchanged")
            .map((s) => (
              <div key={s.section_key} className="card">
                <strong>{s.section_key}</strong> ({s.status})
                {s.sentences
                  .filter((o) => o.op !== "equal")
                  .map((o, i) => (
                    <div key={i}>
                      {o.old.map((t, j) => (
                        <p key={"o" + j} className="diff-del">
                          − {t}
                        </p>
                      ))}
                      {o.new.map((t, j) => (
                        <p key={"n" + j} className="diff-add">
                          + {t}
                        </p>
                      ))}
                    </div>
                  ))}
              </div>
            ))}
        </div>
      )}
    </section>
  );
}
