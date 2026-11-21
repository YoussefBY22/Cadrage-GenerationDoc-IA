"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import Shell from "@/components/Shell";
import { api } from "@/lib/api";
import type { Dossier } from "@/lib/api-types";
import { t } from "@/lib/i18n/fr";
import { useGuard } from "@/lib/useGuard";

export default function DossiersPage() {
  const guard = useGuard();
  const [dossiers, setDossiers] = useState<Dossier[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [client, setClient] = useState("");

  useEffect(() => {
    api
      .listDossiers()
      .then(setDossiers)
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
    } catch (err) {
      setError(guard(err));
    }
  };

  return (
    <Shell>
      <h1>{t.dossiers.title}</h1>
      {error && <p role="alert">{error}</p>}
      {dossiers?.length === 0 && <p>{t.dossiers.empty}</p>}
      <ul className="cards">
        {dossiers?.map((d) => (
          <li key={d.id} className="card">
            <strong>{d.name}</strong> — {d.client_name}{" "}
            <Link href={`/dossiers/${d.id}`}>{t.dossiers.open}</Link>
          </li>
        ))}
      </ul>
      <form onSubmit={create} className="card row">
        <input
          placeholder={t.dossiers.name}
          aria-label={t.dossiers.name}
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          placeholder={t.dossiers.client}
          aria-label={t.dossiers.client}
          value={client}
          onChange={(e) => setClient(e.target.value)}
          required
        />
        <button type="submit">{t.dossiers.create}</button>
      </form>
    </Shell>
  );
}
