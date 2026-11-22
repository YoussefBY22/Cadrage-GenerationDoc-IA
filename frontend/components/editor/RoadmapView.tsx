"use client";

import { AlertTriangle, ChevronRight, Flag, Route, Save } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Alert, Empty } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import { deliverables } from "./client";
import { m } from "./i18n";
import type { Deliverable, RoadmapResult } from "./types";

interface Edit {
  scores: Record<string, number>;
  duration?: number;
  depends?: string;
}

const errText = (e: unknown) => (e instanceof ApiError ? e.message : t.common.error);

export default function RoadmapView({ id }: { id: string }) {
  const [d, setD] = useState<Deliverable | null>(null);
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setD(await deliverables.get(id));
      setEdits({});
    } catch (e) {
      setError(errText(e));
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);

  const roadmap: RoadmapResult | null = d?.content.roadmap ?? null;
  const editable = d?.state === "draft";

  const patchEdit = (iid: string, f: (e: Edit) => Edit) =>
    setEdits((all) => ({ ...all, [iid]: f(all[iid] ?? { scores: {} }) }));

  const save = async () => {
    setError(null);
    try {
      const initiatives = Object.entries(edits).map(([iid, e]) => ({
        id: iid,
        ...(Object.keys(e.scores).length
          ? { scores: Object.entries(e.scores).map(([key, value]) => ({ key, value })) }
          : {}),
        ...(e.duration !== undefined ? { duration_weeks: e.duration } : {}),
        ...(e.depends !== undefined
          ? { depends_on: e.depends.split(",").map((x) => x.trim()).filter(Boolean) }
          : {}),
      }));
      await deliverables.patchRoadmap(id, initiatives);
      await load();
    } catch (e) {
      setError(errText(e));
    }
  };

  if (!d) return <p role={error ? "alert" : undefined}>{error ?? t.common.loading}</p>;
  const c = m.roadmapCols;
  if (!roadmap)
    return <Empty icon={Route} label={m.noRoadmap} />;

  const sorted = [...roadmap.items].sort((a, b) => a.rank - b.rank);
  const title = (iid: string) => roadmap.items.find((x) => x.initiative.id === iid)?.initiative.title ?? iid;
  const waves = [...new Set(sorted.map((x) => x.wave))].sort((a, b) => a - b);
  const maxScore = Math.max(...sorted.map((x) => x.score), 1);

  return (
    <section>
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href={`/dossiers/${d.dossier_id}`}>{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
          </div>
          <h1>{m.roadmap}</h1>
        </div>
        {editable && (
          <div className="actions">
            <button className="btn btn-dark" disabled={Object.keys(edits).length === 0} onClick={save}>
              <Save size={16} />
              {m.saveRoadmap}
            </button>
          </div>
        )}
      </div>
      {roadmap.cycles.map((cycle, i) => (
        <div key={i} className="toast err" role="alert" data-testid="cycle-alert">
          <AlertTriangle size={16} />
          {m.cycleAlert(cycle.join(" → "))}
        </div>
      ))}
      {error && <Alert>{error}</Alert>}

      <div className="card" style={{ marginBottom: 20, display: "grid", gap: 12 }}>
        {waves.map((w) => (
          <div key={w} className="wave-lane">
            <span className="wave">{c.wave} {w}</span>
            {sorted
              .filter((x) => x.wave === w)
              .map((x) => (
                <span key={x.initiative.id} className={`chip${roadmap.critical_path.includes(x.initiative.id) ? " crit-path" : ""}`}>
                  {x.initiative.title}
                </span>
              ))}
          </div>
        ))}
        {roadmap.critical_path.length > 0 && (
          <div className="wave-lane muted" style={{ borderTop: "1px solid var(--line)", paddingTop: 10 }}>
            <Flag size={14} />
            <b style={{ color: "var(--ink)" }}>{m.criticalPath}</b>
            {roadmap.critical_path.map(title).join(" → ")}
          </div>
        )}
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{c.rank}</th>
              <th>{c.wave}</th>
              <th>{c.title}</th>
              <th>{c.score}</th>
              <th>{c.explain}</th>
              <th>{c.duration}</th>
              <th>{c.depends}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(({ initiative: ini, score, rank, wave }) => (
              <tr key={ini.id} data-testid={`row-${ini.id}`}>
                <td>
                  <span className="rank">{rank}</span>
                </td>
                <td>
                  <span className="wave">{wave}</span>
                </td>
                <td style={{ fontWeight: 600, minWidth: 180 }}>{ini.title}</td>
                <td>
                  <span className="score">{score.toFixed(2)}</span>
                  <span className="score-bar">
                    <i style={{ width: `${Math.round((score / maxScore) * 100)}%` }} />
                  </span>
                </td>
                <td>
                  <div className="crit">
                    {roadmap.criteria.map((cr) => {
                      const sc = ini.scores.find((s) => s.key === cr.key);
                      return (
                        <label key={cr.key} title={sc?.rationale ?? ""} style={{ display: "contents" }}>
                          <span>
                            {cr.label} · {Math.round(cr.weight * 100)} %
                          </span>
                          <input
                            type="number"
                            min={1}
                            max={5}
                            disabled={!editable}
                            aria-label={`${ini.title} ${cr.label}`}
                            value={edits[ini.id]?.scores[cr.key] ?? sc?.value ?? 1}
                            onChange={(e) =>
                              patchEdit(ini.id, (x) => ({
                                ...x,
                                scores: { ...x.scores, [cr.key]: Number(e.target.value) },
                              }))
                            }
                          />
                        </label>
                      );
                    })}
                  </div>
                </td>
                <td>
                  <input
                    type="number"
                    min={1}
                    className="mini-input"
                    disabled={!editable}
                    aria-label={`${ini.title} ${c.duration}`}
                    value={edits[ini.id]?.duration ?? ini.duration_weeks ?? ""}
                    onChange={(e) => patchEdit(ini.id, (x) => ({ ...x, duration: Number(e.target.value) }))}
                  />
                </td>
                <td>
                  <input
                    disabled={!editable}
                    aria-label={`${ini.title} ${c.depends}`}
                    value={edits[ini.id]?.depends ?? ini.depends_on.join(", ")}
                    onChange={(e) => patchEdit(ini.id, (x) => ({ ...x, depends: e.target.value }))}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
