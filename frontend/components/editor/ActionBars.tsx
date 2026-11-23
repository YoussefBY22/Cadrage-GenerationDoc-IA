"use client";

import { Check, Download, Lock, Send, Undo2, X } from "lucide-react";
import { useState } from "react";
import { m } from "./i18n";
import type { ExportFormat } from "./client";
import type { DeliverableState, Role } from "./types";

type Target = { to: DeliverableState; label: string; needsReason?: boolean; reviewerOnly?: boolean };

const ICONS = { in_review: Send, approved: Check, rejected: X, draft: Undo2 } as const;

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

  const targets = transitionsFor(state).filter((tg) => !tg.reviewerOnly || role !== "consultant");

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
      <span className={`badge ${state}`} data-testid="state">
        {m.state[state]}
      </span>
      {targets.map((tg) => {
        const Icon = ICONS[tg.to];
        return (
          <button
            key={tg.to + tg.label}
            className={`btn btn-sm${tg.to === "approved" ? " btn-primary" : ""}`}
            onClick={() => (tg.needsReason ? setPending(tg) : onTransition(tg.to))}
          >
            <Icon size={14} />
            {tg.label}
          </button>
        );
      })}
      {pending && (
        <>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={m.reason}
            aria-label={m.reason}
          />
          <button className="btn btn-dark btn-sm" onClick={confirm}>
            {m.confirm}
          </button>
        </>
      )}
      {error && <span role="alert">{error}</span>}
    </div>
  );
}

/** Acquittement par un relecteur : un motif est toujours exigé (le serveur refuse sinon). */
export function AckBar({
  items,
  onAck,
}: {
  items: { index: number; label: string }[];
  onAck: (index: number, reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  if (items.length === 0) return null;
  return (
    <div className="row">
      <input
        className="grow"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder={m.ackReason}
        aria-label={m.ackReason}
      />
      {items.map((it) => (
        <button
          key={it.index}
          className="btn btn-sm"
          disabled={!reason.trim()}
          onClick={() => {
            onAck(it.index, reason.trim());
            setReason("");
          }}
        >
          {it.label}
        </button>
      ))}
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
        <button key={f} className="btn btn-sm" disabled={!enabled} onClick={() => onExport(f)}>
          <Download size={14} />
          {f.toUpperCase()}
        </button>
      ))}
      {!enabled && (
        <small className="row" style={{ gap: 4 }}>
          <Lock size={12} />
          {m.exportHint}
        </small>
      )}
    </div>
  );
}
