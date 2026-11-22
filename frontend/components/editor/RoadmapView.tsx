"use client";

import { AlertTriangle, ChevronRight, CircleCheck, Flag, Info, Route, Save } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useDossier } from "@/lib/useDossier";
import SourcePanel from "@/components/SourcePanel";
import { Alert, Empty } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { ExistingProject, Finding, Priority } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { deliverables } from "./client";
import { m } from "./i18n";
import type { Chain, Coherence, CoherenceIssue, Deliverable, RoadmapResult } from "./types";

interface Edit {
  scores: Record<string, number>;
  duration?: number;
  depends?: string[];
  accept?: boolean;
  priorities?: string[];
  projects?: string[];
}

const errText = (e: unknown) => (e instanceof ApiError ? e.message : t.common.error);

export default function RoadmapView({ id }: { id: string }) {
  const [d, setD] = useState<Deliverable | null>(null);
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const [error, setError] = useState<string | null>(null);
  const [coh, setCoh] = useState<Coherence | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [projects, setProjects] = useState<ExistingProject[]>([]);
  const [source, setSource] = useState<string | null>(null);
  const dossier = useDossier(d?.dossier_id);

  const load = useCallback(async () => {
    try {
      const del = await deliverables.get(id);
      setD(del);
      setEdits({});
      // La cohérence se recalcule à chaque lecture, sur l'état actuel des constats, priorités et projets.
      const [c, f, p, j] = await Promise.all([
        deliverables.coherence(id).catch(() => null),
        api.listFindings(del.dossier_id).catch(() => []),
        api.listPriorities(del.dossier_id).catch(() => []),
        api.listProjects(del.dossier_id).catch(() => []),
      ]);
      setCoh(c);
      setFindings(f);
      setPriorities(p);
      setProjects(j);
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
        ...(e.depends !== undefined ? { depends_on: e.depends } : {}),
        ...(e.accept !== undefined ? { accept_proposal: e.accept } : {}),
        ...(e.priorities !== undefined ? { priority_ids: e.priorities } : {}),
        ...(e.projects !== undefined ? { depends_on_projects: e.projects } : {}),
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
  const cc = t.coeur.coherence;
  const validPriorities = priorities.filter((p) => p.status === "validated");
  const names: Record<string, string> = {
    ...Object.fromEntries(roadmap.items.map((x) => [x.initiative.id, x.initiative.title])),
    ...Object.fromEntries(findings.map((f) => [f.id, f.text])),
    ...Object.fromEntries(priorities.map((p) => [p.id, p.title])),
    ...Object.fromEntries(projects.map((p) => [p.id, p.title])),
  };
  const nm = (x: unknown) => names[String(x)] ?? String(x);
  const detail = (i: CoherenceIssue): string => {
    const r = i.refs;
    switch (i.code) {
      case "FINDING_NO_INITIATIVE":
        return nm(r.finding_id);
      case "PRIORITY_NO_INITIATIVE":
        return nm(r.priority_id);
      case "INITIATIVE_UNANCHORED":
        return `${nm(r.initiative_id)} (${(r.missing as string[]).map((k) => cc.missing[k] ?? k).join(", ")})`;
      case "INITIATIVE_DUPLICATES_PROJECT":
        return `${nm(r.initiative_id)} ≈ ${nm(r.project_id)}`;
      case "DEPENDENCY_ORDER":
        return (r.initiative_ids as string[]).map(nm).join(" → ");
      case "INHERITED_PRIORITY":
        return `${nm(r.initiative_id)} · ${cc.inherited(Number(r.inherited_rank))}`;
      case "SCORE_TIE":
        return `${(r.initiative_ids as string[]).map(nm).join(", ")} · ${cc.tiedBy(cc.tie[String(r.decided_by)] ?? String(r.decided_by))}`;
      case "NO_DURATION":
        return nm(r.initiative_id);
      default:
        return "";
    }
  };
  const badge = { blocking: "rejected", warning: "warn", info: "draft" } as const;
  const groups = Object.entries(
    (coh?.issues ?? []).reduce<Record<string, CoherenceIssue[]>>((acc, i) => {
      (acc[i.code] ??= []).push(i);
      return acc;
    }, {}),
  );
  const chainOf = (iid: string): Chain | undefined => coh?.chains.find((c) => c.initiative_id === iid);
  const toggle = (list: string[], v: string, on: boolean) => (on ? [...list, v] : list.filter((x) => x !== v));

  return (
    <div className={`split${source ? " with-panel" : ""}`}>
    <section>
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href="/dossiers">{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
            <Link href={`/dossiers/${d.dossier_id}`}>{dossier?.name ?? "…"}</Link>
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

      <div className="card" style={{ marginBottom: 20 }} data-testid="coherence">
        <div className="card-head">
          <h2 style={{ margin: 0 }}>{cc.title}</h2>
          {coh && groups.length === 0 && (
            <span className="badge approved">
              <CircleCheck size={13} />
              {cc.ok}
            </span>
          )}
        </div>
        <ul className="coh-list">
          {groups.map(([code, list]) => (
            <li key={code} data-testid={`issue-${code}`}>
              <details className="coh-group">
                <summary>
                  <span className={`badge ${badge[list[0].severity]} plain`}>
                    {list[0].severity === "info" ? <Info size={13} /> : <AlertTriangle size={13} />}
                    {cc.codes[code] ?? code}
                  </span>
                  <b className="count">{list.length}</b>
                </summary>
                <ul className="coh-list" style={{ marginTop: 6 }}>
                  {list.map((i, n) => (
                    <li key={n} className="coh-item">
                      {detail(i)}
                    </li>
                  ))}
                </ul>
                {code === "NO_DURATION" && <small className="muted">{cc.orderOnly}</small>}
              </details>
            </li>
          ))}
        </ul>
        {(roadmap.rejected_links?.length ?? 0) > 0 && (
          <div style={{ marginTop: 12 }} data-testid="rejected-links">
            <b>{cc.rejected}</b>
            <ul className="coh-list" style={{ marginTop: 6 }}>
              {roadmap.rejected_links?.map((r, n) => (
                <li key={n} className="coh-item">
                  <span className="tag">{r.kind}</span>
                  <span>
                    {r.initiative} : {r.value}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {(roadmap.passages_not_sent ?? 0) > 0 && (
          <p className="muted" role="note" style={{ marginBottom: 0 }}>
            {cc.notSent(roadmap.passages_not_sent ?? 0)}
          </p>
        )}
      </div>

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
              <th>{c.duration}</th>
              <th>{c.depends}</th>
              <th>{cc.links}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(({ initiative: ini, score, rank, wave, unscored }) => (
              <tr key={ini.id} data-testid={`row-${ini.id}`}>
                <td>
                  <span className="rank">{rank}</span>
                </td>
                <td>
                  <span className="wave">{wave}</span>
                </td>
                <td style={{ fontWeight: 600, minWidth: 200 }}>
                  {ini.title}
                  <details className="picker" style={{ fontWeight: 400 }}>
                    <summary>{c.explain}</summary>
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
                              value={edits[ini.id]?.scores[cr.key] ?? sc?.value ?? ""}
                              placeholder="–"
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
                  </details>
                </td>
                <td>
                  {unscored && unscored.length > 0 ? (
                    <span className="badge draft plain" title={unscored.join(", ")}>
                      {t.coeur.unscored}
                    </span>
                  ) : (
                    <>
                      <span className="score">{score.toFixed(2)}</span>
                      <span className="score-bar">
                        <i style={{ width: `${Math.round((score / maxScore) * 100)}%` }} />
                      </span>
                    </>
                  )}
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
                  <details className="picker">
                    <summary>
                      {(edits[ini.id]?.depends ?? ini.depends_on).length
                        ? (edits[ini.id]?.depends ?? ini.depends_on).map(title).join(", ")
                        : "–"}
                    </summary>
                    {sorted
                      .filter((o) => o.initiative.id !== ini.id)
                      .map((o) => (
                        <label key={o.initiative.id}>
                          <input
                            type="checkbox"
                            disabled={!editable}
                            checked={(edits[ini.id]?.depends ?? ini.depends_on).includes(o.initiative.id)}
                            onChange={(e) =>
                              patchEdit(ini.id, (x) => ({
                                ...x,
                                depends: toggle(x.depends ?? ini.depends_on, o.initiative.id, e.target.checked),
                              }))
                            }
                          />
                          {o.initiative.title}
                        </label>
                      ))}
                  </details>
                </td>
                <td>
                  <details className="picker">
                    <summary>
                      {cc.links} (
                      {(edits[ini.id]?.priorities ?? ini.priority_ids ?? []).length +
                        (edits[ini.id]?.projects ?? ini.depends_on_projects ?? []).length}
                      )
                    </summary>
                    {validPriorities.length > 0 && <small className="muted">{cc.priorities}</small>}
                    {validPriorities.map((p) => (
                      <label key={p.id}>
                        <input
                          type="checkbox"
                          disabled={!editable}
                          checked={(edits[ini.id]?.priorities ?? ini.priority_ids ?? []).includes(p.id)}
                          onChange={(e) =>
                            patchEdit(ini.id, (x) => ({
                              ...x,
                              priorities: toggle(x.priorities ?? ini.priority_ids ?? [], p.id, e.target.checked),
                            }))
                          }
                        />
                        {p.title}
                      </label>
                    ))}
                    {projects.length > 0 && <small className="muted">{t.coeur.projects}</small>}
                    {projects.map((p) => (
                      <label key={p.id}>
                        <input
                          type="checkbox"
                          disabled={!editable}
                          checked={(edits[ini.id]?.projects ?? ini.depends_on_projects ?? []).includes(p.id)}
                          onChange={(e) =>
                            patchEdit(ini.id, (x) => ({
                              ...x,
                              projects: toggle(x.projects ?? ini.depends_on_projects ?? [], p.id, e.target.checked),
                            }))
                          }
                        />
                        {p.title}
                      </label>
                    ))}
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-title" style={{ margin: "24px 0 12px" }}>
        <h2>{cc.chains}</h2>
      </div>
      <div className="cards">
        {sorted.map(({ initiative: ini }) => {
          const ch = chainOf(ini.id);
          if (!ch) return null;
          return (
            <article key={ini.id} className="card chain" data-testid={`chain-${ini.id}`}>
              <div className="card-head">
                <b>
                  {ch.position}. {ch.title}
                </b>
                <span className="muted">
                  {ch.start_week != null && ch.end_week != null ? cc.weeks(ch.start_week, ch.end_week) : cc.orderOnly}
                  {ch.inherited_rank != null && ` · ${cc.inherited(ch.inherited_rank)}`}
                </span>
              </div>
              <div className="chain-row">
                <span>{cc.findings}</span>
                <span>
                  {ch.findings.map((f) => (
                    <span key={f.id} style={{ display: "block" }}>
                      {f.title}
                    </span>
                  ))}
                </span>
              </div>
              <div className="chain-row">
                <span>{t.coeur.proposal}</span>
                <span className="row" style={{ gap: 8 }}>
                  <span className={`badge ${ch.proposal_status === "accepted" ? "approved" : "warn"}`}>
                    {ch.proposal_status === "accepted" ? t.coeur.accepted : t.coeur.proposal}
                  </span>
                  {ch.proposal_flags.length > 0 && ch.proposal_status !== "accepted" && (
                    <span className="badge warn plain" data-testid={`flags-${ini.id}`}>
                      <AlertTriangle size={13} />
                      {t.coeur.unsourced(ch.proposal_flags.join(", "))}
                    </span>
                  )}
                  {editable && (
                    <button
                      className="btn btn-sm"
                      onClick={() =>
                        void deliverables
                          .patchRoadmap(id, [{ id: ini.id, accept_proposal: ch.proposal_status !== "accepted" }])
                          .then(load)
                          .catch((e) => setError(errText(e)))
                      }
                    >
                      {ch.proposal_status === "accepted" ? t.common.cancel : t.coeur.accept}
                    </button>
                  )}
                </span>
              </div>
              <div className="chain-row">
                <span>{cc.objective}</span>
                <span>{ch.objective || "–"}</span>
              </div>
              <div className="chain-row">
                <span>{cc.result}</span>
                <span>{ch.expected_result || "–"}</span>
              </div>
              <div className="chain-row">
                <span>{cc.indicator}</span>
                <span>{ch.indicator || "–"}</span>
              </div>
              <div className="chain-row">
                <span>{cc.priorities}</span>
                <span>{ch.priorities.length ? ch.priorities.map((p) => `#${p.kind} ${p.title}`).join(" ; ") : "–"}</span>
              </div>
              <div className="chain-row">
                <span>{cc.dependencies}</span>
                <span>
                  {ch.dependencies.length
                    ? ch.dependencies
                        .map((d) =>
                          d.kind === "project" ? `${d.title} (${t.coeur.projectState[String(d.extra.state)] ?? ""})` : d.title,
                        )
                        .join(" ; ")
                    : "–"}
                </span>
              </div>
              <div className="chain-row">
                <span>{cc.sources}</span>
                <span className="row" style={{ gap: 6 }}>
                  {ch.source_ids.length === 0 && "–"}
                  {ch.source_ids.map((sid, n) => (
                    <button key={sid} className="link" onClick={() => setSource(sid)}>
                      [{n + 1}]
                    </button>
                  ))}
                </span>
              </div>
            </article>
          );
        })}
      </div>
    </section>
    {source && <SourcePanel chunkId={source} onClose={() => setSource(null)} />}
    </div>
  );
}
