"use client";

import { Check, RotateCcw, Play, TriangleAlert, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import ContextGauge from "@/components/ContextGauge";
import Shell from "@/components/Shell";
import { Alert } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { ContextBudget, Limits, ModelCard, ModelsOverview, TestReport } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useGuard } from "@/lib/useGuard";

const fmt = (n: number | null | undefined) => (n == null ? t.models.l.unknown : n.toLocaleString("fr-FR"));
const gb = (n: number | null) => (n == null ? "—" : `${(n / 1e9).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ${t.models.l.gb}`);
const tokens = (n: number | null | undefined) => (n == null ? t.models.l.unknown : `${fmt(n)} ${t.models.l.tokens}`);

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="kv">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function LimitCards({ limits }: { limits: Limits }) {
  const l = t.models.l;
  const vision = limits.model.vision;
  return (
    <div className="limits">
      <section className="card">
        <h3>{t.models.limits.model}</h3>
        <dl>
          <Row label={l.maxContext}>{tokens(limits.model.max_context)}</Row>
          <Row label={l.images}>{vision ? l.imagesYes : vision === false ? l.imagesNo : l.unknown}</Row>
          <Row label={l.capabilities}>{limits.model.capabilities?.join(", ") ?? l.unknown}</Row>
        </dl>
      </section>
      <section className="card">
        <h3>{t.models.limits.engine}</h3>
        <dl>
          <Row label={l.allocated}>
            <b>{tokens(limits.engine.allocated_context)}</b>{" "}
            <span className="muted">({limits.engine.allocated_source === "config" ? l.fromConfig : l.fromDefault})</span>
          </Row>
          {limits.engine.loaded_context != null && <Row label={l.loaded}>{tokens(limits.engine.loaded_context)}</Row>}
          <Row label={l.vram}>{gb(limits.engine.vram_bytes)}</Row>
          {limits.engine.gpu_layers != null && <Row label={l.gpu}>{limits.engine.gpu_layers}</Row>}
        </dl>
      </section>
      <section className="card">
        <h3>{t.models.limits.app}</h3>
        <dl>
          <Row label={l.reserved}>{tokens(limits.app.response_reserved)}</Row>
          <Row label={l.upload}>{limits.app.max_upload_mb} Mo</Row>
          <Row label={l.formats}>{limits.app.formats.join(", ")}</Row>
          <Row label={l.saturation}>
            <ul className="plain">
              {limits.app.saturation.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </Row>
        </dl>
      </section>
    </div>
  );
}

function TestBadge({ model }: { model: ModelCard }) {
  const test = model.test;
  if (!test) return <span className="badge plain draft">{t.models.notTested}</span>;
  if (!test.up_to_date) return <span className="badge warn">{t.models.stale}</span>;
  return test.passed ? (
    <span className="badge approved">{t.models.passed}</span>
  ) : (
    <span className="badge rejected">{t.models.failed}</span>
  );
}

function Checks({ checks }: { checks: TestReport["checks"] }) {
  return (
    <ul className="checks">
      {checks.map((c) => (
        <li key={c.key} className={c.status}>
          {c.status === "pass" ? <Check size={14} /> : c.status === "warn" ? <TriangleAlert size={14} /> : <X size={14} />}
          <span>{c.label}</span>
          {c.detail && <em>{c.detail}</em>}
        </li>
      ))}
    </ul>
  );
}

export default function ModelsPage() {
  const guard = useGuard();
  const [data, setData] = useState<ModelsOverview | null>(null);
  const [budget, setBudget] = useState<ContextBudget | null>(null);
  const [candidates, setCandidates] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await api.listModels();
      setData(d);
      setBudget(d.context);
      setCandidates((c) => c ?? Math.round(d.context.passages + d.context.passages_unsent));
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setForbidden(true);
      else setError(guard(e));
    }
  }, [guard]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (candidates == null) return;
    api
      .contextBudget(candidates)
      .then(setBudget)
      .catch(() => {});
  }, [candidates]);

  const run = async (key: string, fn: () => Promise<unknown>, done?: string) => {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await fn();
      if (done) setNotice(done);
    } catch (e) {
      setError(guard(e));
    } finally {
      await load();
      setBusy(null);
    }
  };

  if (forbidden)
    return (
      <Shell>
        <Alert>{t.models.forbidden}</Alert>
      </Shell>
    );

  const active = data?.models.find((m) => m.active);
  return (
    <Shell>
      <div className="page-head">
        <div>
          <h1>{t.models.title}</h1>
          <p className="muted">{t.models.sub}</p>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}
      {notice && <div className="toast ok">{notice}</div>}
      {data?.engine.demo && <div className="toast warn">{t.models.demo}</div>}
      {data && !data.engine.demo && !data.engine.reachable && <Alert>{t.models.engineDown}</Alert>}
      {!data && !error && <p className="muted">{t.common.loading}</p>}
      {data && (
        <>
          <section className="card active-card">
            <div>
              <div className="kpi-label">{t.models.active}</div>
              <div className="active-name">{data.engine.demo ? "—" : (data.active ?? t.models.none)}</div>
              {active && !data.engine.demo && (
                <div className="row">
                  {[active.parameter_size, active.quantization, gb(active.size_bytes)].filter(Boolean).map((x) => (
                    <span key={x} className="tag">
                      {x}
                    </span>
                  ))}
                </div>
              )}
            </div>
            {data.previous && !data.engine.demo && (
              <button type="button" className="btn" disabled={busy !== null} onClick={() => run("rollback", () => api.rollbackModel(), t.models.rollbackDone)}>
                <RotateCcw size={15} />
                {t.models.rollback} {data.previous}
              </button>
            )}
          </section>

          <section className="card">
            <div className="card-head">
              <h2>{t.models.gauge}</h2>
              <span className="muted gauge-sizes">
                {t.models.allocated} <b>{fmt(data.limits.engine.allocated_context)}</b> · {t.models.max} <b>{fmt(data.limits.model.max_context)}</b> ·{" "}
                {t.models.reserved} <b>{fmt(data.limits.app.response_reserved)}</b>
              </span>
            </div>
            {budget && <ContextGauge budget={budget} />}
            <label className="sim">
              {t.models.simulate}
              <input type="range" min={0} max={20000} step={500} value={candidates ?? 0} onChange={(e) => setCandidates(Number(e.target.value))} />
              <b>{fmt(candidates)}</b>
            </label>
            <p className="muted small">{t.models.estimated}</p>
          </section>

          <LimitCards limits={data.limits} />

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.models.table.model}</th>
                  <th>{t.models.table.ctx}</th>
                  <th>{t.models.table.test}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.models.map((m) => (
                  <tr key={m.name}>
                    <td>
                      <b>{m.name}</b> {m.active && <span className="badge approved">{t.models.activeBadge}</span>}
                      <div className="muted small">{[gb(m.size_bytes), m.quantization].filter(Boolean).join(" · ")}</div>
                      <details>
                        <summary>{t.models.details}</summary>
                        <dl className="tech">
                          <Row label={t.models.family}>{[m.family, m.parameter_size].filter(Boolean).join(" ") || "—"}</Row>
                          <Row label={t.models.digest}>{m.digest.slice(0, 19)}</Row>
                          <Row label={t.models.licence}>{m.license ?? "—"}</Row>
                          {m.test?.tokens_per_second != null && <Row label={t.models.speed}>{m.test.tokens_per_second.toLocaleString("fr-FR")}</Row>}
                        </dl>
                        {m.test && <Checks checks={m.test.checks} />}
                      </details>
                    </td>
                    <td>{fmt(m.max_context)}</td>
                    <td>
                      <TestBadge model={m} />
                    </td>
                    <td className="actions">
                      {m.role === "embedding" ? (
                        <span className="muted small">{t.models.embedding}</span>
                      ) : (
                        <>
                          <button type="button" className="btn btn-sm" disabled={busy !== null || data.engine.demo} onClick={() => run(`t:${m.name}`, () => api.testModel(m.name))}>
                            <Play size={13} />
                            {busy === `t:${m.name}` ? t.models.testing : t.models.test}
                          </button>
                          {!m.active && (
                            <button
                              type="button"
                              className="btn btn-sm btn-primary"
                              disabled={busy !== null || data.engine.demo || !m.test?.passed || !m.test.up_to_date}
                              onClick={() => run(`a:${m.name}`, () => api.activateModel(m.name), t.models.activated)}
                            >
                              {t.models.activate}
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.history.length > 0 && (
            <details className="card hist">
              <summary>{t.models.history}</summary>
              <ul className="plain">
                {data.history.map((h, i) => (
                  <li key={i}>
                    <span className="muted">{h.at.replace("T", " ").slice(0, 16)}</span> {h.action} — <b>{h.model}</b>
                    {h.by && <span className="muted"> ({h.by})</span>}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </Shell>
  );
}
