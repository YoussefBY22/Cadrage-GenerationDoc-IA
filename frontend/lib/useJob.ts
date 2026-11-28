"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Job } from "@/lib/api-types";

/** Suit une tâche longue d'un dossier : la reprend si elle tourne déjà (page rechargée), interroge le
 * serveur chaque seconde tant qu'elle tourne, et prévient quand elle se termine. */
export function useJob(dossierId: string, kind: Job["kind"], onFinished?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const finished = useRef(onFinished);
  finished.current = onFinished;

  useEffect(() => {
    api
      .listJobs(dossierId)
      .then((list) => {
        const run = list.find((j) => j.kind === kind && j.status === "running");
        if (run) setJob(run);
      })
      .catch(() => {});
  }, [dossierId, kind]);

  const running = job?.status === "running";
  const id = job?.id;
  useEffect(() => {
    if (!running || !id) return;
    const timer = window.setInterval(() => {
      api
        .getJob(id)
        .then((j) => {
          setJob(j);
          if (j.status !== "running") finished.current?.(j);
        })
        .catch(() => {});
    }, 1000);
    return () => window.clearInterval(timer);
  }, [running, id]);

  const start = useCallback(async () => {
    setError(null);
    try {
      setJob(await api.startJob(dossierId, kind));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [dossierId, kind]);

  const cancel = useCallback(async () => {
    if (id) setJob(await api.cancelJob(id));
  }, [id]);

  return { job, start, cancel, error, running, dismiss: () => setJob(null) };
}
