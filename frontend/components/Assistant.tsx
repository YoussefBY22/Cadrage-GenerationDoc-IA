"use client";

import { CircleStop, FileText, MessageCircle, Send, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import WaitNote from "@/components/WaitNote";
import { api } from "@/lib/api";
import type { AssistantAnswer } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useViewerOpener } from "@/lib/viewerLink";

interface Msg {
  role: "user" | "assistant";
  text: string;
  sources?: AssistantAnswer["sources"];
  model?: boolean;
}

/** L'aide de la page affichée : réponse instantanée à « à quoi sert cette page ? ». */
function pageHelp(path: string): string {
  if (/^\/dossiers\/[^/]+\/findings/.test(path)) return t.findings.hint + " " + t.findings.extractHelp;
  if (/^\/dossiers\/[^/]+\/recommendations/.test(path)) return t.projet.recosHint;
  if (/^\/dossiers\/[^/]+\/context/.test(path)) return t.context.hint;
  if (/^\/dossiers\/[^/]+\/decisions/.test(path)) return t.decisions.hint;
  if (/^\/dossiers\/[^/]+\/priorities/.test(path)) return t.coeur.prioritiesHint;
  if (/^\/dossiers\/[^/]+\/projects/.test(path)) return t.coeur.projectsHint;
  if (/^\/dossiers\/[^/]+\/search/.test(path)) return t.search.hint + " " + t.search.howTo;
  if (/^\/dossiers\/[^/]+$/.test(path)) return t.dossier.hint;
  if (/^\/deliverables\/[^/]+\/roadmap/.test(path)) return t.assistant.roadmapHelp;
  if (/^\/deliverables\//.test(path)) return t.assistant.deliverableHelp;
  if (/^\/admin\/models/.test(path)) return t.assistant.modelsHelp;
  return t.assistant.dashboardHelp;
}

/** Assistant présent sur toutes les pages (bulle en bas à droite). */
export default function Assistant({ dossierId }: { dossierId?: string }) {
  const path = usePathname();
  const viewer = useViewerOpener();
  const key = `cadrage.assistant.${dossierId ?? "general"}`;
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [waiting, setWaiting] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const list = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      setMsgs(JSON.parse(window.sessionStorage.getItem(key) ?? "[]") as Msg[]);
    } catch {
      setMsgs([]);
    }
  }, [key]);
  useEffect(() => {
    try {
      window.sessionStorage.setItem(key, JSON.stringify(msgs.slice(-30)));
    } catch {
      /* stockage indisponible : l'historique reste en mémoire */
    }
    list.current?.scrollTo({ top: list.current.scrollHeight, behavior: "smooth" });
  }, [msgs, key, waiting]);

  const send = async (e?: FormEvent, text?: string) => {
    e?.preventDefault();
    const message = (text ?? draft).trim();
    if (!message || waiting) return;
    const history = msgs.slice(-6).map((m) => ({ role: m.role, text: m.text }));
    setMsgs((m) => [...m, { role: "user", text: message }]); // le message apparaît tout de suite
    setDraft("");
    setWaiting(true);
    const ctrl = new AbortController();
    abort.current = ctrl;
    try {
      const r = await api.assistant(dossierId ?? null, { message, history, page_help: pageHelp(path) }, ctrl.signal);
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, sources: r.sources, model: r.model }]);
    } catch (err) {
      const stopped = err instanceof DOMException && err.name === "AbortError";
      setMsgs((m) => [...m, { role: "assistant", text: stopped ? t.assistant.stopped : t.assistant.failed }]);
    } finally {
      setWaiting(false);
      abort.current = null;
    }
  };

  if (!open)
    return (
      <button type="button" className="assistant-fab" onClick={() => setOpen(true)} aria-label={t.assistant.open}>
        <MessageCircle size={20} />
        {t.assistant.title}
      </button>
    );

  return (
    <section className="assistant" aria-label={t.assistant.title}>
      {viewer.modal}
      <header>
        <MessageCircle size={16} />
        <b>{t.assistant.title}</b>
        <button type="button" className="btn btn-ghost btn-icon" onClick={() => setOpen(false)} aria-label={t.common.close}>
          <X size={16} />
        </button>
      </header>
      <div className="assistant-msgs" ref={list}>
        {msgs.length === 0 && (
          <div className="assistant-intro">
            <p>{dossierId ? t.assistant.intro : t.assistant.introGeneral}</p>
            <div className="assistant-chips">
              {(dossierId ? t.assistant.examples : [t.assistant.examples[0]]).map((x) => (
                <button key={x} type="button" className="chip" onClick={() => void send(undefined, x)}>
                  {x}
                </button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`assistant-msg ${m.role}`}>
            <p>{m.text}</p>
            {m.role === "assistant" && m.model === false && <small className="muted">{t.assistant.instant}</small>}
            {(m.sources?.length ?? 0) > 0 && (
              <div className="assistant-sources">
                {m.sources!.map((s) => (
                  <button
                    key={s.chunk_id}
                    type="button"
                    className="chip"
                    title={s.excerpt}
                    onClick={() => void viewer.open({ docId: s.document_id, page: s.page })}
                  >
                    <FileText size={12} /> {s.label}
                    {s.page ? ` · p. ${s.page}` : ""}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {waiting && (
          <div className="assistant-msg assistant">
            <WaitNote label={t.wait.chat} typical={t.wait.chatTypical} />
          </div>
        )}
      </div>
      <form onSubmit={(e) => void send(e)} className="assistant-form">
        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={t.assistant.placeholder} aria-label={t.assistant.placeholder} disabled={waiting} />
        {waiting ? (
          <button type="button" className="btn btn-sm danger" onClick={() => abort.current?.abort()}>
            <CircleStop size={14} />
            {t.job.stop}
          </button>
        ) : (
          <button type="submit" className="btn btn-primary btn-sm" disabled={!draft.trim()}>
            <Send size={14} />
          </button>
        )}
      </form>
    </section>
  );
}
