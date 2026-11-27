"use client";

import { ExternalLink, PanelTop } from "lucide-react";
import { useCallback, useState } from "react";
import { t } from "@/lib/i18n";

/** Canal entre l'application et les onglets « document » déjà ouverts (même navigateur). */
export const CHANNEL = "cadrage-viewer";
const WINDOW = "cadrage-document";

export interface ShowMessage {
  type: "show";
  docId: string;
  page?: number | null;
  findingId?: string | null;
  recoId?: string | null;
}

/** Demande aux onglets ouverts s'ils affichent déjà un document (réponse en < 200 ms). */
function anyViewerOpen(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof BroadcastChannel === "undefined") return resolve(false);
    const ch = new BroadcastChannel(CHANNEL);
    const timer = window.setTimeout(() => {
      ch.close();
      resolve(false);
    }, 200);
    ch.onmessage = (e) => {
      if (e.data?.type === "pong") {
        window.clearTimeout(timer);
        ch.close();
        resolve(true);
      }
    };
    ch.postMessage({ type: "ping" });
  });
}

export const viewerUrl = (m: Omit<ShowMessage, "type">) => {
  const q = new URLSearchParams();
  if (m.page) q.set("page", String(m.page));
  if (m.findingId) q.set("finding", m.findingId);
  if (m.recoId) q.set("reco", m.recoId);
  return `/documents/${m.docId}?${q.toString()}`;
};

/** Ouvre une preuve dans la visionneuse. Si un onglet document est déjà ouvert, demande :
 * l'afficher là-bas (le surlignage est remplacé) ou ouvrir un nouvel onglet. */
export function useViewerOpener() {
  const [pending, setPending] = useState<Omit<ShowMessage, "type"> | null>(null);

  const open = useCallback(async (m: Omit<ShowMessage, "type">) => {
    if (await anyViewerOpen()) setPending(m);
    else window.open(viewerUrl(m), WINDOW);
  }, []);

  const inExisting = () => {
    if (!pending) return;
    const ch = new BroadcastChannel(CHANNEL);
    ch.postMessage({ type: "show", ...pending } satisfies ShowMessage);
    ch.close();
    window.open("", WINDOW)?.focus(); // ramène l'onglet nommé au premier plan, sans le recharger
    setPending(null);
  };
  const inNew = () => {
    if (pending) window.open(viewerUrl(pending), "_blank");
    setPending(null);
  };

  const modal = pending ? (
    <div className="modal-back" role="dialog" aria-modal="true" aria-label={t.viewer.choiceTitle}>
      <div className="modal card">
        <h3>{t.viewer.choiceTitle}</h3>
        <p className="muted">{t.viewer.choiceText}</p>
        <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-ghost" onClick={() => setPending(null)}>
            {t.common.cancel}
          </button>
          <button type="button" className="btn" onClick={inNew}>
            <ExternalLink size={15} />
            {t.viewer.newTab}
          </button>
          <button type="button" className="btn btn-primary" onClick={inExisting} autoFocus>
            <PanelTop size={15} />
            {t.viewer.sameTab}
          </button>
        </div>
      </div>
    </div>
  ) : null;

  return { open, modal };
}
