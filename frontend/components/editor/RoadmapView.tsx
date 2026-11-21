"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { deliverables } from "./client";
import { m } from "./i18n";
import type { Deliverable, RoadmapResult } from "./types";

interface Edit {
  scores: Record<string, number>;
  duration?: number;
  depends?: string;
}

const errText = (e: unknown) => (e instanceof ApiError ? e.message : "Une erreur est survenue");

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

  if (!d) return <p role={error ? "alert" : undefined}>{error ?? "Chargement…"}</p>;
  if (!roadmap) return <p>{m.roadmap} : aucune donnée.</p>;
  const c = m.roadmapCols;

  return (
    <section>
      <h1>{m.roadmap}</h1>
      {roadmap.cycles.map((cycle, i) => (
        <p key={i} role="alert" data-testid="cycle-alert">
          {m.cycleAlert(cycle.join(" → "))}
        </p>
      ))}
      {error && <p role="alert">{error}</p>}
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
          {[...roadmap.items]
            .sort((a, b) => a.rank - b.rank)
            .map(({ initiative: ini, score, rank, wave }) => (
              <tr key={ini.id} data-testid={`row-${ini.id}`}>
                <td>{rank}</td>
                <td>{wave}</td>
                <td>{ini.title}</td>
                <td>{score.toFixed(2)}</td>
                <td>
                  {roadmap.criteria.map((cr) => {
                    const sc = ini.scores.find((s) => s.key === cr.key);
                    return (
                      <label key={cr.key} title={sc?.rationale ?? ""} style={{ display: "block" }}>
                        {cr.label} ({Math.round(cr.weight * 100)} %){" "}
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
                          style={{ width: "3.5rem" }}
                        />
                      </label>
                    );
                  })}
                </td>
                <td>
                  <input
                    type="number"
                    min={1}
                    disabled={!editable}
                    aria-label={`${ini.title} ${c.duration}`}
                    value={edits[ini.id]?.duration ?? ini.duration_weeks ?? ""}
                    onChange={(e) =>
                      patchEdit(ini.id, (x) => ({ ...x, duration: Number(e.target.value) }))
                    }
                    style={{ width: "4.5rem" }}
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
      {roadmap.critical_path.length > 0 && (
        <p>
          {m.criticalPath} : {roadmap.critical_path.join(" → ")}
        </p>
      )}
      {editable && (
        <button disabled={Object.keys(edits).length === 0} onClick={save}>
          {m.saveRoadmap}
        </button>
      )}
    </section>
  );
}
