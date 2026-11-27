"use client";

import { Check, ChevronRight, ListChecks, Plus, RotateCcw, ScanSearch, Trash2, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { AuditRecommendation, RecommendationsOverview, ReportRecommendations } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useDossier } from "@/lib/useDossier";
import { useGuard } from "@/lib/useGuard";
import { useViewerOpener } from "@/lib/viewerLink";

const BADGE: Record<string, string> = { proposed: "draft", validated: "approved", deleted: "rejected", merged: "in_review" };
const CHECK: Record<string, string> = { ok: "approved", ecart: "rejected", non_detectees: "rejected", non_lu: "draft" };

function Report({ r, run, dossierId, onOpen }: { r: ReportRecommendations; run: (fn: () => Promise<unknown>) => void; dossierId: string; onOpen: (m: { docId: string; page?: number | null; recoId?: string }) => Promise<void> }) {
  const [title, setTitle] = useState("");
  const [num, setNum] = useState("");
  const [page, setPage] = useState("");
  const actives = r.recommendations.filter((x) => x.status === "proposed" || x.status === "validated");
  const c = r.check;

  const add = (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    run(async () => {
      await api.addRecommendation(dossierId, {
        document_id: r.document_id,
        title: title.trim(),
        number: num ? Number(num) : null,
        page: page ? Number(page) : null,
      });
      setTitle("");
      setNum("");
      setPage("");
    });
  };

  const label = (x: AuditRecommendation) => `${x.number ? `n° ${x.number} – ` : ""}${x.title}`;

  return (
    <section className="card" style={{ marginTop: 16 }} data-testid={`report-${r.document_id}`}>
      <div className="card-head">
        <div style={{ minWidth: 0 }}>
          <h3 style={{ margin: 0 }}>{r.filename}</h3>
          <small className="muted">{t.projet.expected(c.expected, c.extracted)}</small>
        </div>
        <span className={`badge ${CHECK[c.status]}`} data-testid="check-status">
          {c.status !== "ok" && <TriangleAlert size={13} />}
          {t.projet.status[c.status]}
        </span>
      </div>
      {(c.missing.length > 0 || c.duplicates.length > 0) && (
        <p className="muted" data-testid="check-detail">
          {c.missing.length > 0 && t.projet.missing(c.missing)}
          {c.missing.length > 0 && c.duplicates.length > 0 && " · "}
          {c.duplicates.length > 0 && t.projet.duplicates(c.duplicates)}
        </p>
      )}
      {c.status === "non_detectees" && (
        <button type="button" className="btn btn-sm" onClick={() => run(() => api.setNoRecommendation(dossierId, r.document_id, true))}>
          {t.projet.noneConfirm}
        </button>
      )}
      {r.recommendations.length > 0 && (
        <div className="table-wrap reco-table" style={{ marginTop: 10 }}>
          <table>
            <thead>
              <tr>
                <th>{t.projet.number}</th>
                <th>{t.projet.title}</th>
                <th>{t.projet.page}</th>
                <th>{t.coeur.statusField}</th>
              </tr>
            </thead>
            <tbody>
              {r.recommendations.map((x) => {
                const active = x.status === "proposed" || x.status === "validated";
                return (
                  <tr key={x.id} data-testid={`reco-${x.id}`} style={active ? undefined : { opacity: 0.55 }}>
                    <td className="num">{x.number ?? "–"}</td>
                    <td id={x.id}>
                      <b>{x.title}</b>
                      {x.intro && <p className="reco-intro">{x.intro}</p>}
                      {(x.sub_points?.length ?? 0) > 0 && (
                        <ol className="reco-subs">
                          {x.sub_points!.map((sp) => (
                            <li key={sp.label}>
                              <b>{sp.label})</b> {sp.text}
                            </li>
                          ))}
                        </ol>
                      )}
                      {(x.deadline || (x.points?.length ?? 0) > 0) && (
                        <div className="reco-facts">
                          {x.deadline && (
                            <span className="tag" title={t.projet.deadlineHint}>
                              {t.projet.deadline} {x.deadline}
                            </span>
                          )}
                          {(x.points?.length ?? 0) > 0 && (
                            <span className="muted" title={t.projet.pointsHint}>
                              {t.projet.points(compact(x.points!))}
                            </span>
                          )}
                          <Link href={`/dossiers/${dossierId}/findings?reco=${x.id}`} className="link">
                            {t.projet.seeFindings}
                          </Link>
                        </div>
                      )}
                      <div className="muted">
                        {t.projet.origin[x.origin]}
                        {x.status === "merged" && x.merged_into && (
                          <> · {t.projet.mergedInto(label(r.recommendations.find((o) => o.id === x.merged_into) ?? x))}</>
                        )}
                      </div>
                      <div className="reco-actions">
                        {x.status === "proposed" && (
                          <button className="btn btn-sm" onClick={() => run(() => api.patchRecommendation(x.id, { status: "validated" }))}>
                            <Check size={13} />
                            {t.projet.validate}
                          </button>
                        )}
                        {active && actives.length > 1 && (
                          <select
                            className="mini-select"
                            aria-label={`${t.projet.mergeInto} ${label(x)}`}
                            value=""
                            onChange={(e) => e.target.value && run(() => api.patchRecommendation(x.id, { merge_into: e.target.value }))}
                          >
                            <option value="">{t.projet.mergeInto}</option>
                            {actives
                              .filter((o) => o.id !== x.id)
                              .map((o) => (
                                <option key={o.id} value={o.id}>
                                  {label(o).slice(0, 60)}
                                </option>
                              ))}
                          </select>
                        )}
                        {active ? (
                          <button
                            className="btn btn-ghost btn-icon"
                            aria-label={`${t.projet.remove} ${label(x)}`}
                            onClick={() => run(() => api.patchRecommendation(x.id, { status: "deleted" }))}
                          >
                            <Trash2 size={15} />
                          </button>
                        ) : (
                          <button className="btn btn-ghost btn-sm" onClick={() => run(() => api.patchRecommendation(x.id, { status: "proposed" }))}>
                            <RotateCcw size={13} />
                            {x.status === "merged" ? t.projet.unmerge : t.projet.restore}
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="num">
                      {x.page ? (
                        <button type="button" className="link" title={t.findings.openInDoc}
                          onClick={() => void onOpen({ docId: r.document_id, page: x.page, recoId: x.id })}>
                          {x.page}
                        </button>
                      ) : (
                        "–"
                      )}
                    </td>
                    <td>
                      <span className={`badge ${BADGE[x.status]}`}>{t.projet.recoStatus[x.status]}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <form className="form-row" onSubmit={add} style={{ marginTop: 12 }} data-testid={`reco-form-${r.document_id}`}>
        <label style={{ width: 70 }}>
          <span>{t.projet.number}</span>
          <input type="number" min={1} max={99} value={num} onChange={(e) => setNum(e.target.value)} />
        </label>
        <label className="grow">
          <span>{t.projet.addTitle}</span>
          <input value={title} maxLength={500} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label style={{ width: 80 }}>
          <span>{t.projet.page}</span>
          <input type="number" min={1} value={page} onChange={(e) => setPage(e.target.value)} />
        </label>
        <button className="btn" type="submit">
          <Plus size={15} />
          {t.projet.add}
        </button>
      </form>
    </section>
  );
}

/** Recommandations des rapports d'audit : relevé par règles, corrections du consultant, contrôle de cohérence. */
/** [18,19,20,24] → « 18-20, 24 » */
function compact(ns: number[]): string {
  const out: string[] = [];
  let i = 0;
  while (i < ns.length) {
    let j = i;
    while (j + 1 < ns.length && ns[j + 1] === ns[j] + 1) j++;
    out.push(j > i ? `${ns[i]}-${ns[j]}` : `${ns[i]}`);
    i = j + 1;
  }
  return out.join(", ");
}

export default function RecommendationsView({ dossierId }: { dossierId: string }) {
  const guard = useGuard();
  const dossier = useDossier(dossierId);
  const viewer = useViewerOpener();
  const [data, setData] = useState<RecommendationsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api
      .listRecommendations(dossierId)
      .then(setData)
      .catch((e) => setError(guard(e)));
  }, [dossierId, guard]);
  useEffect(load, [load]);

  const run = (fn: () => Promise<unknown>) => {
    setError(null);
    fn()
      .then(load)
      .catch((e) => setError(guard(e)));
  };

  const extract = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await api.extractRecommendations(dossierId));
    } catch (e) {
      setError(guard(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href="/dossiers">{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
            <Link href={`/dossiers/${dossierId}`}>{dossier?.name ?? "…"}</Link>
            <ChevronRight size={14} />
          </div>
          <h1>{t.projet.recos}</h1>
          <small className="muted">{t.projet.recosHint}</small>
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={() => void extract()} disabled={busy} data-testid="recos-extract">
            <ScanSearch size={16} />
            {busy ? t.projet.extracting : t.projet.extract}
          </button>
        </div>
      </div>
      {viewer.modal}
      {error && <Alert>{error}</Alert>}
      {data && data.alerts > 0 && (
        <div className="toast err" role="status" data-testid="recos-alerts">
          <TriangleAlert size={15} /> {t.projet.alertsBanner(data.alerts)}
        </div>
      )}
      {data === null && !error && <p className="muted">{t.common.loading}</p>}
      {data?.reports.length === 0 && <Empty icon={ListChecks} label={t.projet.noReports} />}
      {data?.reports.map((r) => <Report key={r.document_id} r={r} run={run} dossierId={dossierId} onOpen={viewer.open} />)}
    </>
  );
}
