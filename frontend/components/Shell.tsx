"use client";

import {
    Cpu,
  FileCheck2,
  FileText,
  FolderKanban,
  FolderOpen,
  Gavel,
  LayoutDashboard,
  ListChecks,
  ListOrdered,
  LogOut,
  MessageSquare,
  Route,
  Scale,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { LangSwitch, Logo } from "@/components/ui";
import { api, getRole } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getLastDossier, getRefs, setLastDossier, type DossierRefs } from "@/lib/refs";

export function Footer() {
  return <p className="legal">{t.footer}</p>;
}

function NavLink({ href, icon: Icon, label, exact }: { href: string; icon: typeof Search; label: string; exact?: boolean }) {
  const path = usePathname();
  const active = exact ? path === href : path === href || path.startsWith(href + "/");
  return (
    <Link href={href} aria-current={active ? "page" : undefined}>
      <Icon size={17} strokeWidth={1.9} />
      {label}
    </Link>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const params = useParams<{ id?: string }>();
  const path = usePathname();
  const [last, setLast] = useState<string | null>(null);
  const [refs, setRefs] = useState<DossierRefs>({});
  const [admin, setAdmin] = useState(false);
  const onDossier = path.startsWith("/dossiers/");
  const dossierId = onDossier ? params.id : path.startsWith("/deliverables/") ? (last ?? undefined) : undefined;

  useEffect(() => {
    if (onDossier && params.id) setLastDossier(params.id);
    setLast(getLastDossier());
  }, [onDossier, params.id]);

  useEffect(() => {
    setAdmin(getRole() === "admin");
  }, [path]);

  useEffect(() => {
    if (!dossierId) return;
    setRefs(getRefs(dossierId));
    // Le serveur fait foi : le livrable le plus récent de chaque type.
    api
      .listDeliverables(dossierId)
      .then((list) => {
        const latest = (type: string) => list.find((d) => d.type === type)?.id;
        setRefs((cur) => ({ ...cur, roadmap: latest("roadmap"), tor: latest("tor"), cdc: latest("cdc") }));
      })
      .catch(() => {
        /* hors ligne : on garde la mémoire locale */
      });
  }, [dossierId, path]);

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      /* déjà déconnecté */
    }
    router.push("/login");
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <Link href="/dossiers" aria-label={t.appName} style={{ textDecoration: "none" }}>
          <Logo />
        </Link>
        <nav className="nav" aria-label="Navigation">
          <NavLink href="/dossiers" icon={LayoutDashboard} label={t.nav.dashboard} exact />
          {admin && <NavLink href="/admin/models" icon={Cpu} label={t.nav.models} />}
          {dossierId && (
            <>
              <div className="nav-title">{t.nav.dossiers}</div>
              <NavLink href={`/dossiers/${dossierId}`} icon={FolderOpen} label={t.nav.documents} exact />
              <NavLink href={`/dossiers/${dossierId}/context`} icon={MessageSquare} label={t.nav.context} />
              <NavLink href={`/dossiers/${dossierId}/findings`} icon={ListChecks} label={t.nav.findings} />
              <NavLink href={`/dossiers/${dossierId}/recommendations`} icon={ListOrdered} label={t.nav.recommendations} />
              {refs.roadmap && <NavLink href={`/deliverables/${refs.roadmap}/roadmap`} icon={Route} label={t.nav.roadmap} />}
              {refs.tor && <NavLink href={`/deliverables/${refs.tor}`} icon={FileText} label={t.nav.tor} />}
              {refs.cdc && <NavLink href={`/deliverables/${refs.cdc}`} icon={FileCheck2} label={t.nav.cdc} />}
              <div className="nav-title">{t.nav.inputs}</div>
              <NavLink href={`/dossiers/${dossierId}/decisions`} icon={Gavel} label={t.nav.decisions} />
              <NavLink href={`/dossiers/${dossierId}/priorities`} icon={Scale} label={t.nav.priorities} />
              <NavLink href={`/dossiers/${dossierId}/projects`} icon={FolderKanban} label={t.nav.projects} />
              <NavLink href={`/dossiers/${dossierId}/search`} icon={Search} label={t.nav.search} />
            </>
          )}
        </nav>
        <div className="sidebar-foot">
          <LangSwitch />
          <button type="button" className="btn" onClick={logout}>
            <LogOut size={16} />
            {t.nav.logout}
          </button>
          <Footer />
        </div>
      </aside>
      <main className="content">
        <div className="page">{children}</div>
      </main>
    </div>
  );
}
