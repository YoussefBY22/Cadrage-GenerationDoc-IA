"use client";

import { useState } from "react";
import { m } from "./i18n";
import type { ExportFormat } from "./client";
import type { DeliverableState, Role } from "./types";

type Target = { to: DeliverableState; label: string; needsReason?: boolean; reviewerOnly?: boolean };

/** Boutons de transition offerts selon l'état courant (06 §8) ; le serveur reste l'arbitre. */
export function transitionsFor(state: DeliverableState): Target[] {
  switch (state) {
    case "draft":
      return [{ to: "in_review", label: m.transitions.submit }];
    case "in_review":
      return [
        { to: "approved", label: m.transitions.approve, reviewerOnly: true },
        { to: "rejected", label: m.transitions.reject, needsReason: true, reviewerOnly: true },
        { to: "draft", label: m.transitions.withdraw },
      ];
    case "rejected":
      return [{ to: "draft", label: m.transitions.reopen }];
    default:
      return [];
  }
}

export function TransitionBar({
  state,
  role,
  onTransition,
}: {
  state: DeliverableState;
  role: Role;
  onTransition: (to: DeliverableState, reason?: string) => void;
}) {
  const [pending, setPending] = useState<Target | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const targets = transitionsFor(state).filter((t) => !t.reviewerOnly || role !== "consultant");

  const confirm = () => {
    if (pending?.needsReason && !reason.trim()) {
      setError(m.reasonRequired);
      return;
    }
    onTransition(pending!.to, reason.trim() || undefined);
    setPending(null);
    setReason("");
    setError(null);
  };

  return (
    <div className="row">
      <span className="badge" data-testid="state">
        {m.state[state]}
      </span>
      {targets.map((t) => (
        <button
          key={t.to + t.label}
          onClick={() => (t.needsReason ? setPending(t) : onTransition(t.to))}
        >
          {t.label}
        </button>
      ))}
      {pending && (
        <>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={m.reason}
            aria-label={m.reason}
          />
          <button onClick={confirm}>{m.confirm}</button>
        </>
      )}
      {error && <span role="alert">{error}</span>}
    </div>
  );
}

export function ExportBar({
  state,
  onExport,
}: {
  state: DeliverableState;
  onExport: (format: ExportFormat) => void;
}) {
  const enabled = state === "approved";
  return (
    <div className="row">
      <strong>{m.exports}</strong>
      {(["docx", "pptx", "pdf"] as const).map((f) => (
        <button key={f} disabled={!enabled} onClick={() => onExport(f)}>
          {f.toUpperCase()}
        </button>
      ))}
      {!enabled && <small>{m.exportHint}</small>}
    </div>
  );
}
