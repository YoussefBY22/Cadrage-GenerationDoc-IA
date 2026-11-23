"use client";

import type { ContextBudget } from "@/lib/api-types";
import { t } from "@/lib/i18n";

const fmt = (n: number) => n.toLocaleString("fr-FR");

/**
 * Jauge de la fenêtre de contexte, réutilisable : elle ne fait qu'afficher un `ContextBudget` (docs/api-modeles.md).
 * Système, contexte, passages et réponse remplissent la fenêtre allouée ; les passages non envoyés restent dehors.
 */
export default function ContextGauge({ budget }: { budget: ContextBudget }) {
  const parts = [
    { key: "system", value: budget.system },
    { key: "context", value: budget.context },
    { key: "passages", value: budget.passages },
    { key: "response", value: budget.response_reserved },
    { key: "free", value: budget.free },
  ] as const;
  const total = Math.max(1, budget.window_allocated);
  return (
    <div className="gauge" data-testid="context-gauge">
      <div className="gauge-bar" role="img" aria-label={`${t.models.gauge} : ${fmt(budget.window_allocated)} ${t.models.l.tokens}`}>
        {parts.map((p) => (
          <span key={p.key} className={`seg seg-${p.key}`} style={{ width: `${(p.value / total) * 100}%` }} title={`${t.models.seg[p.key]} : ${fmt(p.value)}`} />
        ))}
      </div>
      <ul className="gauge-legend">
        {parts.map((p) => (
          <li key={p.key}>
            <i className={`seg seg-${p.key}`} aria-hidden />
            {t.models.seg[p.key]} <b>{fmt(p.value)}</b>
          </li>
        ))}
        <li className={budget.passages_unsent > 0 ? "unsent" : undefined}>
          <i className="seg seg-unsent" aria-hidden />
          {t.models.seg.unsent} <b>{fmt(budget.passages_unsent)}</b>
        </li>
      </ul>
      <p className="gauge-note">
        {budget.passages_unsent > 0 ? t.models.unsentNote.replace("{n}", String(budget.passages_unsent_count)) : t.models.fits}
      </p>
    </div>
  );
}
