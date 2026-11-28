"use client";

import "pdfjs-dist/web/pdf_viewer.css";
import { ArrowLeft, Search, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert } from "@/components/ui";
import { api } from "@/lib/api";
import type { AuditRecommendation, DocumentInfo, Finding } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useGuard } from "@/lib/useGuard";
import { CHANNEL, type ShowMessage, viewerUrl } from "@/lib/viewerLink";

/* eslint-disable @typescript-eslint/no-explicit-any -- types de pdf.js chargés dynamiquement */
type Pdf = any;

const MAX_SELECTED = 8;
const COLORS = ["#ffd60a", "#7dd3fc", "#86efac", "#fca5a5", "#c4b5fd", "#fdba74", "#f9a8d4", "#5eead4"];
const HOVER_MAX_MS = 3000;

interface Item {
  id: string;
  kind: "finding" | "reco";
  label: string; // ce qu'on affiche dans la liste et la bulle
  quote: string; // ce qu'on cherche dans le document
  severity?: string;
  page?: number | null;
}
interface Rect {
  page: number;
  x: number;
  y: number;
  w: number;
  h: number;
}
interface PageText {
  norm: string; // texte normalisé de la page
  map: number[]; // position normalisée → indice de l'élément pdf.js
  items: any[];
}

const normalize = (s: string) =>
  s
    .toLowerCase()
    .replace(/[­]/g, "")
    .replace(/[«»"“”]/g, "")
    .replace(/[’]/g, "'")
    .replace(/-\s+/g, "")
    .replace(/\s+/g, " ")
    .trim();

function pageText(content: any): PageText {
  let norm = "";
  const map: number[] = [];
  content.items.forEach((it: any, i: number) => {
    const piece = normalize(String(it.str ?? ""));
    if (!piece) return;
    if (norm && !norm.endsWith(" ")) {
      norm += " ";
      map.push(i);
    }
    for (let k = 0; k < piece.length; k++) {
      norm += piece[k];
      map.push(i);
    }
  });
  return { norm, map, items: content.items };
}

/** Pages et éléments pdf.js qui contiennent la citation (entière, sinon son début ou sa fin). */
function locate(texts: PageText[], quote: string): { page: number; items: Set<number> }[] {
  const q = normalize(quote);
  if (q.length < 12) return [];
  const probes = [q, q.slice(0, 70), q.slice(-70), q.slice(0, 40)];
  for (const probe of probes) {
    if (probe.length < 12) continue;
    for (let p = 0; p < texts.length; p++) {
      const k = texts[p].norm.indexOf(probe);
      if (k >= 0) {
        const items = new Set<number>();
        for (let j = k; j < k + probe.length && j < texts[p].map.length; j++) items.add(texts[p].map[j]);
        const out = [{ page: p + 1, items }];
        // citation complète coupée par une fin de page : la suite est au début de la page suivante
        if (probe === q.slice(0, 70) && p + 1 < texts.length) {
          const tail = q.slice(-50);
          const k2 = texts[p + 1].norm.indexOf(tail);
          if (k2 >= 0 && k2 < 600) {
            const it2 = new Set<number>();
            for (let j = k2; j < k2 + tail.length; j++) it2.add(texts[p + 1].map[j]);
            out.push({ page: p + 2, items: it2 });
          }
        }
        return out;
      }
    }
  }
  return [];
}

export default function EvidenceViewer({ docId, page, findingId, recoId }: { docId: string; page: number; findingId: string | null; recoId: string | null }) {
  const guard = useGuard();
  const router = useRouter();
  const [doc, setDoc] = useState<DocumentInfo | null>(null);
  const [pdf, setPdf] = useState<Pdf | null>(null);
  const [lib, setLib] = useState<any>(null);
  const [texts, setTexts] = useState<PageText[]>([]);
  const [sizes, setSizes] = useState<{ w: number; h: number }[]>([]);
  const [width, setWidth] = useState(820);
  const [measured, setMeasured] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<string[]>([findingId ?? recoId ?? ""].filter(Boolean));
  const [tab, setTab] = useState<"finding" | "reco">(recoId ? "reco" : "finding");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; ids: string[] } | null>(null);
  const tipTimer = useRef<number | null>(null);
  const selecting = useRef(false);
  const scroller = useRef<HTMLDivElement>(null);
  const rendered = useRef<Map<number, number>>(new Map()); // page → largeur rendue
  const tasks = useRef<Map<number, any>>(new Map());
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const firstScroll = useRef(false);

  // ---- chargement : document, fichier, constats et recommandations du dossier --------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const d = await api.getDocument(docId);
        if (cancelled) return;
        setDoc(d);
        document.title = d.title || d.filename;
        const [blob, fs, recos] = await Promise.all([
          api.documentFile(docId),
          api.listFindings(d.dossier_id).catch(() => [] as Finding[]),
          api.listRecommendations(d.dossier_id).catch(() => null),
        ]);
        const list: Item[] = [
          ...fs
            .filter((f) => !f.merged_into && f.status !== "discarded" && (f.sources ?? []).some((s) => s.document_id === docId))
            .map((f) => ({
              id: f.id,
              kind: "finding" as const,
              label: f.text,
              quote: f.quote ?? f.text,
              severity: f.severity,
              page: f.sources?.find((s) => s.document_id === docId)?.page_start ?? null,
            })),
          ...(recos?.reports ?? [])
            .filter((r) => r.document_id === docId)
            .flatMap((r) => r.recommendations)
            .filter((x: AuditRecommendation) => x.status === "proposed" || x.status === "validated")
            .map((x: AuditRecommendation) => ({
              id: x.id,
              kind: "reco" as const,
              label: `${t.viewer.reco} ${x.number ?? "–"} — ${x.title}`,
              quote: x.title,
              page: x.page,
            })),
        ];
        setItems(list);
        const pdfjs: any = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
        const loaded = await pdfjs.getDocument({ data: new Uint8Array(await blob.arrayBuffer()) }).promise;
        if (cancelled) return;
        setLib(pdfjs);
        setPdf(loaded);
        const ts: PageText[] = [];
        const ss: { w: number; h: number }[] = [];
        for (let p = 1; p <= loaded.numPages; p++) {
          const pg = await loaded.getPage(p);
          const vp = pg.getViewport({ scale: 1 });
          ss.push({ w: vp.width, h: vp.height });
          ts.push(pageText(await pg.getTextContent()));
        }
        if (!cancelled) {
          setSizes(ss);
          setTexts(ts);
        }
      } catch (e) {
        if (!cancelled) setError(guard(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docId, guard]);

  // ---- largeur disponible -------------------------------------------------------------------------
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setWidth(Math.max(320, Math.min(980, el.clientWidth - 32)));
      setMeasured(true);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ---- surlignages : rectangles de chaque élément sélectionné ------------------------------------
  const found = useMemo(() => {
    const out: Record<string, { page: number; items: Set<number> }[]> = {};
    if (!texts.length) return out;
    for (const it of items) out[it.id] = locate(texts, it.quote);
    return out;
  }, [items, texts]);

  const rects = useCallback(
    (pageNo: number, scale: number): (Rect & { id: string; color: string })[] => {
      if (!lib || !texts[pageNo - 1]) return [];
      const out: (Rect & { id: string; color: string })[] = [];
      selected.forEach((id, n) => {
        for (const hit of found[id] ?? []) {
          if (hit.page !== pageNo) continue;
          const vpT = [scale, 0, 0, -scale, 0, sizes[pageNo - 1].h * scale];
          hit.items.forEach((i) => {
            const it = texts[pageNo - 1].items[i];
            if (!it?.transform) return;
            const tx = lib.Util.transform(vpT, it.transform);
            const h = Math.hypot(tx[2], tx[3]);
            out.push({ page: pageNo, x: tx[4], y: tx[5] - h, w: it.width * scale, h: h * 1.15, id, color: COLORS[n % COLORS.length] });
          });
        }
      });
      return out;
    },
    [lib, texts, selected, found, sizes],
  );

  // ---- rendu des pages visibles (canvas + couche de texte sélectionnable) ------------------------
  const renderPage = useCallback(
    async (p: number) => {
      if (!pdf || !lib || rendered.current.get(p) === width) return;
      const host = pageRefs.current[p];
      if (!host) return;
      rendered.current.set(p, width);
      tasks.current.get(p)?.cancel(); // une page redessinée à une autre largeur : l'ancien rendu est annulé
      const pg = await pdf.getPage(p);
      const scale = width / sizes[p - 1].w;
      const vp = pg.getViewport({ scale });
      const canvas = host.querySelector("canvas") as HTMLCanvasElement;
      const ratio = window.devicePixelRatio || 1;
      canvas.width = vp.width * ratio;
      canvas.height = vp.height * ratio;
      canvas.style.width = `${vp.width}px`;
      canvas.style.height = `${vp.height}px`;
      const ctx = canvas.getContext("2d")!;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      const task = pg.render({ canvasContext: ctx, viewport: vp });
      tasks.current.set(p, task);
      try {
        await task.promise;
      } catch {
        return; // rendu annulé : un plus récent a pris la place
      }
      const layer = host.querySelector(".textLayer") as HTMLDivElement;
      layer.replaceChildren();
      layer.style.setProperty("--scale-factor", String(scale));
      try {
        await new lib.TextLayer({ textContentSource: await pg.getTextContent(), container: layer, viewport: vp }).render();
      } catch {
        /* sans couche de texte : la page reste lisible, seule la sélection manque */
      }
    },
    [pdf, lib, width, sizes],
  );

  useEffect(() => {
    if (!pdf || !sizes.length) return;
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && void renderPage(Number((e.target as HTMLElement).dataset.page))),
      { root: scroller.current, rootMargin: "800px 0px" },
    );
    Object.values(pageRefs.current).forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, [pdf, sizes, renderPage, width]);

  // ---- aller au premier surlignage (ou à la page demandée) ---------------------------------------
  const goTo = useCallback(
    (id: string | null, fallbackPage?: number | null) => {
      const hit = id ? found[id]?.[0] : undefined;
      const p = hit?.page ?? fallbackPage ?? null;
      if (!p || !sizes[p - 1]) return;
      const scale = width / sizes[p - 1].w;
      const r = id ? rects(p, scale).find((x) => x.id === id) : undefined;
      const host = pageRefs.current[p];
      const sc = scroller.current;
      if (host && sc) {
        const top = host.getBoundingClientRect().top - sc.getBoundingClientRect().top + sc.scrollTop;
        sc.scrollTo({ top: top + (r ? r.y - 120 : 0) - 16, behavior: "smooth" });
      }
    },
    [found, sizes, width, rects],
  );

  useEffect(() => {
    if (firstScroll.current || !texts.length || !measured) return;
    firstScroll.current = true;
    window.setTimeout(() => goTo(selected[0] ?? null, page), 120); // après la mise en page à la bonne largeur
  }, [texts, goTo, selected, page, measured]);

  // ---- onglet déjà ouvert : répondre aux autres pages, recevoir une nouvelle preuve --------------
  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const ch = new BroadcastChannel(CHANNEL);
    ch.onmessage = (e) => {
      const m = e.data as ShowMessage | { type: "ping" };
      if (m.type === "ping") ch.postMessage({ type: "pong", docId });
      if (m.type === "show") {
        if (m.docId !== docId) {
          router.push(viewerUrl(m));
          return;
        }
        const id = m.findingId ?? m.recoId ?? null;
        setSelected(id ? [id] : []); // l'ancien surlignage est remplacé par le nouveau
        if (m.recoId) setTab("reco");
        else if (m.findingId) setTab("finding");
        window.setTimeout(() => goTo(id, m.page), 80);
      }
    };
    return () => ch.close();
  }, [docId, router, goTo]);

  // ---- sélection dans la liste -------------------------------------------------------------------
  const toggle = (id: string) =>
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur.length >= MAX_SELECTED ? cur : [...cur, id]));

  // ---- bulle au survol : suit la souris, disparaît après 3 s ou à la sélection de texte ---------
  const onMove = (e: React.MouseEvent, p: number) => {
    if (selecting.current || !sizes[p - 1]) return;
    const box = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
    const x = e.clientX - box.left;
    const y = e.clientY - box.top;
    const ids = [...new Set(rects(p, width / sizes[p - 1].w).filter((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h).map((r) => r.id))];
    if (!ids.length) {
      if (tip) setTip(null);
      if (tipTimer.current) window.clearTimeout(tipTimer.current);
      tipTimer.current = null;
      return;
    }
    if (tipTimer.current === null) {
      tipTimer.current = window.setTimeout(() => setTip((cur) => (cur ? { ...cur, ids: [] } : cur)), HOVER_MAX_MS);
    }
    setTip((cur) => (cur && cur.ids.length === 0 ? cur : { x: e.clientX, y: e.clientY, ids }));
  };
  const onLeave = () => {
    setTip(null);
    if (tipTimer.current) window.clearTimeout(tipTimer.current);
    tipTimer.current = null;
  };

  const byId = Object.fromEntries(items.map((i) => [i.id, i]));
  const visible = items
    .filter((i) => i.kind === tab)
    .filter((i) => !query || normalize(i.label).includes(normalize(query)))
    .sort((a, b) => (a.page ?? 999) - (b.page ?? 999));
  const counts = { finding: items.filter((i) => i.kind === "finding").length, reco: items.filter((i) => i.kind === "reco").length };

  return (
    <div className="ev">
      <aside className="ev-side">
        <div className="ev-head">
          {doc && (
            <Link href={`/dossiers/${doc.dossier_id}/findings`} className="btn btn-ghost btn-sm">
              <ArrowLeft size={14} />
              {t.nav.back}
            </Link>
          )}
          <b className="ev-title" title={doc?.filename}>
            {doc ? doc.title || doc.filename : t.common.loading}
          </b>
        </div>
        <p className="muted small">{t.viewer.hint(MAX_SELECTED)}</p>
        <div className="filter" role="group">
          <button type="button" aria-pressed={tab === "finding"} onClick={() => setTab("finding")}>
            {t.viewer.findings(counts.finding)}
          </button>
          <button type="button" aria-pressed={tab === "reco"} onClick={() => setTab("reco")}>
            {t.viewer.recos(counts.reco)}
          </button>
        </div>
        <label className="ev-search">
          <Search size={14} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.viewer.filter} aria-label={t.viewer.filter} />
        </label>
        {selected.length > 0 && (
          <div className="ev-selection">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b className="small">{t.viewer.selection}</b>
              <button type="button" className="link small" onClick={() => setSelected([])}>
                <X size={12} /> {t.viewer.clear(selected.length)}
              </button>
            </div>
            {selected.map((id, n) =>
              byId[id] ? (
                <button key={id} type="button" className="ev-sel" style={{ borderLeftColor: COLORS[n % COLORS.length] }} onClick={() => goTo(id, byId[id].page)}>
                  {byId[id].label}
                  {texts.length > 0 && !(found[id]?.length) && <small className="muted"> · {t.viewer.notFound}</small>}
                </button>
              ) : null,
            )}
          </div>
        )}
        <ul className="ev-list">
          {visible.map((i) => {
            const n = selected.indexOf(i.id);
            const miss = texts.length > 0 && !(found[i.id]?.length);
            return (
              <li key={i.id} className={n >= 0 ? "on" : ""} style={n >= 0 ? { borderLeftColor: COLORS[n % COLORS.length] } : undefined}>
                <label>
                  <input type="checkbox" checked={n >= 0} disabled={n < 0 && selected.length >= MAX_SELECTED} onChange={() => toggle(i.id)} />
                  <span>
                    <button type="button" className="ev-item" onClick={() => (n >= 0 ? goTo(i.id, i.page) : (toggle(i.id), window.setTimeout(() => goTo(i.id, i.page), 60)))}>
                      {i.label}
                    </button>
                    <small className="muted">
                      {i.page ? `p. ${i.page}` : ""}
                      {miss && ` · ${t.viewer.notFound}`}
                    </small>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </aside>
      <main className="ev-doc" ref={scroller}>
        {error && <Alert>{error}</Alert>}
        {!pdf && !error && <p className="muted" style={{ padding: 20 }}>{t.viewer.loading}</p>}
        {sizes.map((s, k) => {
          const p = k + 1;
          const scale = width / s.w;
          const rs = rects(p, scale);
          return (
            <div
              key={p}
              className="ev-page"
              data-page={p}
              ref={(el) => {
                pageRefs.current[p] = el;
              }}
              style={{ width: s.w * scale, height: s.h * scale }}
              onMouseMove={(e) => onMove(e, p)}
              onMouseLeave={onLeave}
              onMouseDown={() => {
                selecting.current = true;
                setTip(null);
              }}
              onMouseUp={() => {
                selecting.current = false;
              }}
            >
              <canvas />
              {rs.map((r, j) => (
                <i key={j} className="ev-hl" style={{ left: r.x, top: r.y, width: r.w, height: r.h, background: r.color }} />
              ))}
              <div className="textLayer" />
              <span className="ev-pno">{p}</span>
            </div>
          );
        })}
      </main>
      {tip && tip.ids.length > 0 && (
        <div className="ev-tip" style={{ left: Math.min(tip.x + 16, window.innerWidth - 380), top: tip.y + 18 }} role="tooltip">
          {tip.ids.map((id) => (
            <p key={id}>
              <i style={{ background: COLORS[selected.indexOf(id) % COLORS.length] }} />
              {byId[id]?.label}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
