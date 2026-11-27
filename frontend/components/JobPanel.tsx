"use client";

import { ChevronDown, ChevronRight, CircleCheck, CircleStop, CircleX, LoaderCircle, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Job } from "@/lib/api-types";
import { t } from "@/lib/i18n";

export const clock = (s: number) => {
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}` : `${m}:${String(r).padStart(2, "0")}`;
};

/** Bloc de suivi d'une tâche longue : ce qui se passe maintenant, avancement, temps, arrêt, historique. */
export default function JobPanel({ job, onCancel, onClose }: { job: Job; onCancel: () => void; onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  const [tick, setTick] = useState(0);
  const base = useRef({ at: Date.now(), elapsed: job.elapsed_s });
  const list = useRef<HTMLOListElement>(null);

  useEffect(() => {
    base.current = { at: Date.now(), elapsed: job.elapsed_s };
  }, [job.elapsed_s]);
  useEffect(() => {
    if (job.status !== "running") return;
    const timer = window.setInterval(() => setTick((x) => x + 1), 1000);
    return () => window.clearInterval(timer);
  }, [job.status]);
  useEffect(() => {
    if (open && list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [open, job.steps?.length]);

  const running = job.status === "running";
  const elapsed = running ? base.current.elapsed + (Date.now() - base.current.at) / 1000 : job.elapsed_s;
  void tick;
  const pct = job.total ? Math.min(100, Math.round((job.done / job.total) * 100)) : null;
  const Icon = running ? LoaderCircle : job.status === "done" ? CircleCheck : job.status === "cancelled" ? CircleStop : CircleX;

  return (
    <section className={`card job job-${job.status}`} data-testid="job-panel" aria-live="polite">
      <div className="job-head">
        <Icon size={18} className={running ? "spin" : undefined} />
        <b>{job.label}</b>
        <span className="muted">— {t.job.status[job.status]}</span>
        <span className="job-times">
          {t.job.elapsed} {clock(elapsed)}
          {running && (
            <>
              {" · "}
              {job.remaining_s != null ? `${t.job.remaining} ~${clock(job.remaining_s)}` : t.job.estimating}
            </>
          )}
        </span>
        {running ? (
          <button type="button" className="btn btn-sm danger" onClick={onCancel} disabled={job.cancel_requested} data-testid="job-cancel">
            <CircleStop size={14} />
            {job.cancel_requested ? t.job.stopping : t.job.stop}
          </button>
        ) : (
          onClose && (
            <button type="button" className="btn btn-ghost btn-icon" onClick={onClose} aria-label={t.common.close}>
              <X size={15} />
            </button>
          )
        )}
      </div>
      <p className="job-now">{job.error ?? job.current}</p>
      {job.total != null && (
        <div className="job-bar" role="progressbar" aria-valuenow={pct ?? 0} aria-valuemin={0} aria-valuemax={100}>
          <i style={{ width: `${pct ?? 0}%` }} />
          <small>
            {job.done} / {job.total} {job.unit}
          </small>
        </div>
      )}
      {running && <small className="muted">{t.job.note}</small>}
      {(job.steps?.length ?? 0) > 0 && (
        <div className="job-history">
          <button type="button" className="link" onClick={() => setOpen(!open)}>
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {t.job.history(job.steps!.length)}
          </button>
          {open && (
            <ol ref={list}>
              {job.steps!.map((s, i) => (
                <li key={i}>
                  <span className="muted">{clock(s.t)}</span> {s.text}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  );
}
