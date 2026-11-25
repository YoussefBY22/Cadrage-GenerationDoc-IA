"use client";

import { Check, ChevronRight, MessageSquare, Save, Send, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui";
import { api } from "@/lib/api";
import type { ChatReply, ChatTurn, ContextData, ContextSheet, ProjectType } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useDossier } from "@/lib/useDossier";
import { useGuard } from "@/lib/useGuard";

const TYPES: ProjectType[] = ["software", "data_ai", "infrastructure", "supplies", "services", "study", "change", "training"];
const SHORT: (keyof ContextData)[] = ["sector", "size", "country", "language"];
const LONG: (keyof ContextData)[] = ["scope", "constraints", "stakeholders", "roadmap_axes"];
const EMPTY: ContextData = { sector: "", size: "", country: "", language: "", project_types: [], scope: "", constraints: "", stakeholders: "", roadmap_axes: "" };

/** Fiche de contexte (formulaire court) et chat : le chat propose, l'utilisateur confirme. */
export default function ContextView({ dossierId }: { dossierId: string }) {
  const guard = useGuard();
  const dossier = useDossier(dossierId);
  const [sheet, setSheet] = useState<ContextSheet | null>(null);
  const [form, setForm] = useState<ContextData>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [last, setLast] = useState<ChatReply | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api
      .getContext(dossierId)
      .then((s) => {
        setSheet(s);
        setForm(s.data);
      })
      .catch((e) => setError(guard(e)));
  }, [dossierId, guard]);
  useEffect(load, [load]);

  const save = async (confirm: boolean) => {
    setError(null);
    try {
      const s = await api.saveContext(dossierId, { ...form, confirm });
      setSheet(s);
      setForm(s.data);
    } catch (e) {
      setError(guard(e));
    }
  };

  const toggleType = (k: ProjectType) =>
    setForm((f) => ({ ...f, project_types: f.project_types.includes(k) ? f.project_types.filter((x) => x !== k) : [...f.project_types, k] }));

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const text = message.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.chat(dossierId, text, history);
      setHistory([...history, { role: "user", text }, ...(r.reply ? [{ role: "assistant" as const, text: r.reply }] : [])]);
      setLast(r);
      setMessage("");
    } catch (err) {
      setError(guard(err));
    } finally {
      setBusy(false);
    }
  };

  const acceptField = (field: keyof ContextData, value: string | ProjectType[]) => {
    setForm((f) => ({ ...f, [field]: value }));
    setLast((l) => (l ? { ...l, proposals: { ...l.proposals, fields: l.proposals.fields.filter((p) => p.field !== field) } } : l));
  };
  const ignoreDecision = (text: string) =>
    setLast((l) => (l ? { ...l, proposals: { ...l.proposals, decisions: l.proposals.decisions.filter((d) => d.text !== text) } } : l));
  const confirmDecision = async (d: { category: string; text: string }) => {
    setError(null);
    try {
      const made = await api.createDecision(dossierId, { category: d.category as never, text: d.text });
      await api.confirmDecision(made.id);
      ignoreDecision(d.text);
    } catch (err) {
      setError(guard(err));
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
          <h1>{t.context.title}</h1>
          <small className="muted">{t.context.hint}</small>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}

      <div className="split" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))" }}>
        <form className="card stack-form" data-testid="context-form" onSubmit={(e) => { e.preventDefault(); void save(false); }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className={`badge ${sheet?.confirmed ? "approved" : "draft"}`}>
              {sheet?.confirmed ? t.context.confirmedBy(sheet.confirmed_by_name ?? "–", (sheet.confirmed_at ?? "").slice(0, 10)) : t.context.draft}
            </span>
          </div>
          <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }} className="form-row">
            {SHORT.map((k) => (
              <label key={k} className="grow">
                <span>{t.context.fields[k]}</span>
                <input value={form[k] as string} maxLength={200} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              </label>
            ))}
          </div>
          <fieldset style={{ border: 0, padding: 0, margin: "14px 0 0" }}>
            <legend className="muted" style={{ fontSize: 12.5, fontWeight: 600 }}>{t.context.fields.project_types}</legend>
            <div className="row" style={{ marginTop: 6 }}>
              {TYPES.map((k) => (
                <label key={k} className="chip" style={{ cursor: "pointer" }}>
                  <input type="checkbox" checked={form.project_types.includes(k)} onChange={() => toggleType(k)} />
                  {t.context.types[k]}
                </label>
              ))}
            </div>
          </fieldset>
          {LONG.map((k) => (
            <label key={k} style={{ display: "grid", gap: 4, marginTop: 12, fontSize: 12.5, fontWeight: 600 }} className="muted">
              <span>{t.context.fields[k]}</span>
              <textarea rows={2} value={form[k] as string} maxLength={2000} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            </label>
          ))}
          <div className="actions" style={{ marginTop: 16 }}>
            <button className="btn" type="submit">
              <Save size={16} />
              {t.context.save}
            </button>
            <button className="btn btn-primary" type="button" onClick={() => void save(true)}>
              <Check size={16} />
              {t.context.confirm}
            </button>
          </div>
        </form>

        <section className="card" data-testid="chat" aria-label={t.context.chat}>
          <h2 className="section-title" style={{ marginTop: 0 }}>
            <MessageSquare size={16} /> {t.context.chat}
          </h2>
          <p className="muted" style={{ fontSize: 12.5 }}>{t.context.chatNote}</p>
          <div role="log" aria-live="polite" style={{ display: "grid", gap: 8, margin: "12px 0" }}>
            {history.length === 0 && <p className="muted">{t.context.chatEmpty}</p>}
            {history.map((h, i) => (
              <p key={i} style={{ margin: 0, fontWeight: h.role === "user" ? 600 : 400 }}>
                {h.text}
              </p>
            ))}
          </div>
          {last?.status === "refused" && <Alert>{t.context.refused} : {last.reason}</Alert>}
          {last && last.status === "invalid" && <Alert>{last.reason}</Alert>}
          {last?.questions.map((q) => (
            <p key={q} className="muted" style={{ margin: "4px 0" }}>? {q}</p>
          ))}
          {last?.proposals.fields.map((p) => (
            <div key={p.field} className="proposal" data-testid={`proposal-field-${p.field}`}>
              <span className="tag">{t.context.proposal}</span>
              <p>
                <b>{t.context.fields[p.field]}</b> : {Array.isArray(p.value) ? p.value.map((v) => t.context.types[v]).join(", ") : p.value}
              </p>
              <button className="btn btn-sm" type="button" onClick={() => acceptField(p.field, p.value)}>
                {t.context.accept}
              </button>
            </div>
          ))}
          {last?.proposals.decisions.map((d) => (
            <div key={d.text} className="proposal" data-testid="proposal-decision">
              <span className="tag">{d.label}</span>
              <p>{d.text}</p>
              <div className="row">
                <button className="btn btn-sm" type="button" onClick={() => void confirmDecision(d)}>
                  <Check size={13} />
                  {t.context.confirmDecision}
                </button>
                <button className="btn btn-ghost btn-icon" type="button" aria-label={t.context.ignore} onClick={() => ignoreDecision(d.text)}>
                  <X size={14} />
                </button>
              </div>
            </div>
          ))}
          {last && last.dropped.length > 0 && <p className="muted" style={{ fontSize: 12.5 }}>{t.context.dropped(last.dropped.length)}</p>}
          {last && last.sent.history_dropped > 0 && <p className="muted" style={{ fontSize: 12.5 }}>{t.context.notSent(last.sent.history_dropped)}</p>}
          <form className="row" onSubmit={send} style={{ marginTop: 12 }}>
            <input
              className="grow"
              aria-label={t.context.placeholder}
              placeholder={t.context.placeholder}
              value={message}
              maxLength={2000}
              onChange={(e) => setMessage(e.target.value)}
            />
            <button className="btn btn-primary" type="submit" disabled={busy || !message.trim()}>
              <Send size={16} />
              {t.context.send}
            </button>
          </form>
        </section>
      </div>
    </>
  );
}
