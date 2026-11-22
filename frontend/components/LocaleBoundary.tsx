"use client";

import { Fragment, useEffect, type ReactNode } from "react";
import { restoreLocale, useLocale } from "@/lib/i18n";

/** Relit la langue enregistrée, puis remonte l'arbre à chaque bascule FR/EN pour repeindre tous les libellés. */
export default function LocaleBoundary({ children }: { children: ReactNode }) {
  const locale = useLocale();
  useEffect(() => {
    restoreLocale();
  }, []);
  return <Fragment key={locale}>{children}</Fragment>;
}
