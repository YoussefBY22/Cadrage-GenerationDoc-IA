"use client";

import { ArrowUpRight, Building2, CheckCheck, FileText, FolderOpen, ListChecks, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import Shell from "@/components/Shell";
import { Alert, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { Dossier, Severity } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useGuard } from "@/lib/useGuard";

interface Stats {
  documents: number;
  findings: number;
  validated: number;
  sev: Record<Severity, number>;
}

export default function DossiersPage() {
  const guard = useGuard();
  const [dossiers, setDossiers] = useState<Dossier[] | null>(null);
  const [stats, setStats] = useState<Record<string, Stats>>({});
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [client, setClient] = useState("");

  useEffect(() => {
    api
      .listDossiers()
      .then((list) => {
        setDossiers(list);
        // chiffres par dossier : un appel léger par dossier, en parallèle
        list.forEach((d) =>
          Promise.all([api.listDocuments(d.id), api.listFindings(d.id)])
            .then(([docs, findings]) =>
              setStats((s) => ({
                ...s,
                [d.id]: { documents: docs.length, findings: findings.length, validated: findings.filter((f) => f.validated).length,
                  sev: {
                    high: findings.filter((f) => f.severity === "high").length,
                    medium: findings.filter((f) => f.severity === "medium").length,
                    low: findings.filter((f) => f.severity === "low").length,
                  },
                },
              })),
            )
            .catch(() => {}),
        );
      })
      .catch((e) => setError(guard(e)));
  }, [guard]);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const d = await api.createDossier(name, client);
      setDossiers((cur) => [...(cur ?? []), d]);
      setName("");
      setClient("");
      setCreating(false);
    } catch (err) {
      setError(guard(err));
    }
  };

  const all = Object.values(stats);
  const sum = (k: "documents" | "findings" | "validated") => all.reduce((n, s) => n + s[k], 0);
  const sevTotal = (k: Severity) => all.reduce((n, s) => n + s.sev[k], 0);
  const sevAll = Math.max(1, sum("findings"));
  const kpis = [
    { icon: FolderOpen, label: t.dossiers.kpi.dossiers, value: dossiers?.length ?? 0 },
    { icon: FileText, label: t.dossiers.kpi.documents, value: sum("documents") },
    { icon: ListChecks, label: t.dossiers.kpi.findings, value: sum("findings") },
    { icon: CheckCheck, label: t.dossiers.kpi.validated, value: sum("validated") },
  ];

  return (
    <Shell>
      <div className="page-head">
        <h1>{t.dossiers.title}</h1>
        <div className="actions">
          <button className="btn btn-primary" onClick={() => setCreating((v) => !v)}>
            <Plus size={16} />
            {t.common.new}
          </button>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}

      <div className="kpis">
        {kpis.map(({ icon: Icon, label, value }) => (
          <div key={label} className="kpi">
            <div className="kpi-label">
              <Icon size={15} />
              {label}
            </div>
            <div className="kpi-value">{value}</div>
          </div>
        ))}
      </div>

      {creating && (
        <form onSubmit={create} className="card row" style={{ marginBottom: 20 }}>
          <input
            className="grow"
            placeholder={t.dossiers.name}
            aria-label={t.dossiers.name}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            className="grow"
            placeholder={t.dossiers.client}
            aria-label={t.dossiers.client}
            value={client}
            onChange={(e) => setClient(e.target.value)}
            required
          />
          <button type="submit" className="btn btn-dark">
            {t.dossiers.create}
          </button>
        </form>
      )}

      {dossiers?.length === 0 && !creating && (
        <Empty icon={FolderOpen} label={t.dossiers.empty}>
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            <Plus size={16} />
            {t.common.new}
          </button>
        </Empty>
      )}

      <ul className="grid" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {dossiers?.map((d) => {
          const s = stats[d.id];
          const pct = s && s.findings ? Math.round((s.validated / s.findings) * 100) : 0;
          return (
            <li key={d.id}>
              <Link href={`/dossiers/${d.id}`} className="card clickable" aria-label={`${t.dossiers.open} ${d.name}`}>
                <div className="card-head">
                  <h2>{d.name}</h2>
                  <ArrowUpRight size={18} color="var(--grey)" />
                </div>
                <div className="row muted" style={{ gap: 6 }}>
                  <Building2 size={14} />
                  {d.client_name}
                  <span className="tag" style={{ marginLeft: "auto" }}>
                    {d.language.toUpperCase()}
                  </span>
                </div>
                <div className="stats">
                  <span>
                    <FileText size={14} />
                    {s?.documents ?? "–"}
                  </span>
                  <span>
                    <ListChecks size={14} />
                    {s?.findings ?? "–"}
                  </span>
                  <span>
                    <CheckCheck size={14} />
                    {s?.validated ?? "–"}
                  </span>
                </div>
                <div className="progress" aria-hidden>
                  <i style={{ width: `${pct}%` }} />
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
      {all.length > 0 && sum("findings") > 0 && (
        <div className="grid" style={{ marginTop: 24, gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))" }}>
          <section className="card">
            <div className="card-head">
              <h2>{t.findings.title}</h2>
            </div>
            <div className="stack" aria-hidden>
              {(["high", "medium", "low"] as const).map((k) => (
                <i key={k} className={`sev-${k}`} style={{ width: `${(sevTotal(k) / sevAll) * 100}%` }} />
              ))}
            </div>
            <div className="legend" style={{ marginTop: 12 }}>
              {(["high", "medium", "low"] as const).map((k) => (
                <span key={k}>
                  <i className={`dot sev-${k}`} />
                  {t.findings.severity[k]} · <b style={{ color: "var(--ink)" }}>{sevTotal(k)}</b>
                </span>
              ))}
            </div>
          </section>
          <section className="card">
            <div className="card-head">
              <h2>{t.dossiers.kpi.validated}</h2>
            </div>
            <div style={{ display: "grid", gap: 10 }}>
              {dossiers?.map((d) => {
                const s = stats[d.id];
                const pct = s && s.findings ? Math.round((s.validated / s.findings) * 100) : 0;
                return (
                  <div key={d.id} className="bar-row">
                    <span className="bar-label">{d.client_name}</span>
                    <span className="progress" style={{ margin: 0 }}>
                      <i style={{ width: `${pct}%` }} />
                    </span>
                    <b>{pct} %</b>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      )}
    </Shell>
  );
}
