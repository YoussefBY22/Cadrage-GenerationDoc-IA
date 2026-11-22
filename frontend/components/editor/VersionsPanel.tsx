"use client";

import { GitCompare, History, RotateCcw } from "lucide-react";
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
    <section className="card versions">
      <div className="card-head">
        <h2 className="row" style={{ gap: 8 }}>
          <History size={16} />
          {m.versions}
        </h2>
      </div>
      <ul>
        {versions.map((v) => (
          <li key={v.version}>
            <span className="tag">v{v.version}</span>
            <span>{m.origin[v.origin] ?? v.origin}</span>
            <span className="muted">{v.created_at?.slice(0, 16).replace("T", " ") ?? ""}</span>
            {editable && v.version !== last && (
              <button className="btn btn-ghost btn-sm" style={{ marginLeft: "auto" }} onClick={() => onRestore(v.version)}>
                <RotateCcw size={13} />
                {m.restore}
              </button>
            )}
          </li>
        ))}
      </ul>
      <div className="row">
        <label className="row" style={{ gap: 6 }}>
          {m.from}
          <select value={from} onChange={(e) => setFrom(Number(e.target.value))}>
            {options}
          </select>
        </label>
        <label className="row" style={{ gap: 6 }}>
          {m.to}
          <select value={to} onChange={(e) => setTo(Number(e.target.value))}>
            {options}
          </select>
        </label>
        <button className="btn btn-sm" onClick={compare}>
          <GitCompare size={14} />
          {m.compare}
        </button>
      </div>
      {diff && (
        <div data-testid="diff" style={{ marginTop: 12 }}>
          {diff.every((s) => s.status === "unchanged") && <p className="muted">{m.diffNone}</p>}
          {diff
            .filter((s) => s.status !== "unchanged")
            .map((s) => (
              <div key={s.section_key} style={{ marginTop: 8 }}>
                <strong>{s.section_key}</strong> <span className="tag">{s.status}</span>
                {s.sentences
                  .filter((o) => o.op !== "equal")
                  .map((o, i) => (
                    <div key={i}>
                      {o.old.map((tx, j) => (
                        <p key={"o" + j} className="diff-del">
                          − {tx}
                        </p>
                      ))}
                      {o.new.map((tx, j) => (
                        <p key={"n" + j} className="diff-add">
                          + {tx}
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
