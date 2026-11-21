"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n/fr";

export default function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const logout = async () => {
    try {
      await api.logout();
    } catch {
      /* déjà déconnecté */
    }
    router.push("/login");
  };
  return (
    <>
      <header className="topbar">
        <Link href="/dossiers">{t.appName}</Link>
        <button onClick={logout}>{t.nav.logout}</button>
      </header>
      <main>{children}</main>
    </>
  );
}
