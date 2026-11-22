"use client";

import { setLocale, t, useLocale } from "@/lib/i18n";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/** État vide illustré : une pastille, une icône, un libellé court, une action facultative. */
export function Empty({ icon: Icon, label, children, flat }: { icon: LucideIcon; label: string; children?: ReactNode; flat?: boolean }) {
  return (
    <div className={`empty${flat ? " flat" : ""}`}>
      <div className="empty-art" aria-hidden>
        <Icon size={30} strokeWidth={1.6} />
      </div>
      <span>{label}</span>
      {children}
    </div>
  );
}

/** Bascule FR / EN. */
export function LangSwitch() {
  const locale = useLocale();
  return (
    <div className="lang" role="group" aria-label={t.nav.lang}>
      {(["fr", "en"] as const).map((l) => (
        <button key={l} type="button" aria-pressed={locale === l} onClick={() => setLocale(l)}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

export function Logo() {
  return (
    <span className="logo">
      <span className="logo-mark" aria-hidden />
      {t.appName}
    </span>
  );
}

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="toast err" role="alert">
      {children}
    </div>
  );
}
