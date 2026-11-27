"use client";

import { LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { clock } from "@/components/JobPanel";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";

/** Attente courte (une réponse du modèle) : ce qui se passe, temps écoulé, durée habituelle,
 * et si le modèle est déjà pris par une tâche longue, laquelle. */
export default function WaitNote({ label, typical }: { label: string; typical?: string }) {
  const [start] = useState(() => Date.now());
  const [, setTick] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setTick((x) => x + 1), 1000);
    api
      .busy()
      .then((list) => setBusy(list.length ? list.map((j) => (j.total ? `${j.label} (${j.done}/${j.total})` : j.label)).join(", ") : null))
      .catch(() => {});
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="wait-note" role="status" aria-live="polite">
      <LoaderCircle size={16} className="spin" />
      <span>
        {label} — {t.job.elapsed.toLowerCase()} {clock((Date.now() - start) / 1000)}
        {typical && <span className="muted"> · {typical}</span>}
        {busy && <span className="wait-busy">{t.job.busy(busy)}</span>}
      </span>
    </div>
  );
}
