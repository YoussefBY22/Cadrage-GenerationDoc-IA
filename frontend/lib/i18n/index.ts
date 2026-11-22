"use client";

import { useSyncExternalStore } from "react";
import { en } from "./en";
import { fr, type Messages } from "./fr";

export type Locale = "fr" | "en";
const KEY = "cadrage.locale";
const dicts: Record<Locale, Messages> = { fr, en };

let current: Locale = "fr";
const listeners = new Set<() => void>();

/** Dictionnaire courant : `t.x.y` lit toujours la langue active. */
export const t: Messages = new Proxy({} as Messages, {
  get: (_target, prop) => (dicts[current] as unknown as Record<string | symbol, unknown>)[prop],
});

export const getLocale = (): Locale => current;

export function setLocale(l: Locale): void {
  if (l === current) return;
  current = l;
  try {
    window.localStorage.setItem(KEY, l);
  } catch {
    /* stockage indisponible */
  }
  if (typeof document !== "undefined") document.documentElement.lang = l;
  listeners.forEach((fn) => fn());
}

/** Lit la préférence enregistrée (à appeler une fois au montage). */
export function restoreLocale(): void {
  try {
    const saved = window.localStorage.getItem(KEY);
    if (saved === "fr" || saved === "en") setLocale(saved);
  } catch {
    /* ignoré */
  }
}

export function useLocale(): Locale {
  return useSyncExternalStore(
    (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    () => current,
    () => "fr",
  );
}

/** Titre d'une section de gabarit (type « tor », clé « contexte ») dans la langue active. */
export const sectionTitle = (type: string, key: string): string => t.sections[`${type}.${key}`] ?? key;
