"use client";

import { Check, ChevronRight, Plus, Scale, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { Priority } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useDossier } from "@/lib/useDossier";
import { useGuard } from "@/lib/useGuard";

const date = (iso: string | null) => (iso ? iso.slice(0, 10) : "–");

/** Priorités institutionnelles : saisie humaine, rang, statut. Seules les validées servent à générer. */
export default function PrioritiesView({ dossierId }: { dossierId: string }) {
  const guard = useGuard();
  const [items, setItems] = useState<Priority[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [canValidate, setCanValidate] = useState(false);
  const dossier = useDossier(dossierId);

  useEffect(() => {
    api
      .me()
      .then((u) => setCanValidate(u.role === "reviewer" || u.role === "admin"))
      .catch(() => {});
  }, []);

  const load = useCallback(() => {
    api
      .listPriorities(dossierId)
      .then(setItems)
      .catch((e) => setError(guard(e)));
  }, [dossierId, guard]);
  useEffect(load, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      load();
    } catch (e) {
      setError(guard(e));
    }
  };

  const add = (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    void act(async () => {
      await api.createPriority(dossierId, { title: title.trim(), description: description.trim() });
      setTitle("");
      setDescription("");
    });
  };

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href="/dossiers">{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
            <Link href={`/dossiers/${dossierId}`}>{dossier?.name ?? "…"}</Link>
            <ChevronRight size={14} />
          </div>
          <h1>{t.coeur.priorities}</h1>
          <small className="muted">{t.coeur.prioritiesHint}</small>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}

      <form className="card form-row" onSubmit={add} data-testid="priority-form">
        <label>
          <span>{t.coeur.titleField}</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={500} required />
        </label>
        <label className="grow">
          <span>{t.coeur.descriptionField}</span>
          <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={4000} />
        </label>
        <button className="btn btn-primary" type="submit">
          <Plus size={16} />
          {t.coeur.add}
        </button>
      </form>

      <div style={{ marginTop: 20 }}>
        {items === null && !error && <p className="muted">{t.common.loading}</p>}
        {items?.length === 0 && <Empty icon={Scale} label={t.coeur.noPriorities} />}
        {items && items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.coeur.rankField}</th>
                  <th>{t.coeur.titleField}</th>
                  <th>{t.coeur.statusField}</th>
                  <th>{t.coeur.author}</th>
                  <th>{t.coeur.date}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((p) => (
                  <tr key={p.id} data-testid={`priority-${p.id}`}>
                    <td>
                      <input
                        type="number"
                        min={1}
                        className="mini-input"
                        aria-label={`${p.title} ${t.coeur.rankField}`}
                        defaultValue={p.rank}
                        key={`${p.id}-${p.rank}`}
                        onBlur={(e) => {
                          const n = Number(e.target.value);
                          if (n >= 1 && n !== p.rank) void act(() => api.patchPriority(p.id, { rank: n }));
                        }}
                      />
                    </td>
                    <td style={{ minWidth: 220 }}>
                      <b>{p.title}</b>
                      {p.description && <div className="muted">{p.description}</div>}
                    </td>
                    <td>
                      <span className={`badge ${p.status === "validated" ? "approved" : p.status === "rejected" ? "rejected" : "draft"}`}>
                        {t.coeur.priorityStatus[p.status]}
                      </span>
                      {p.validated_by_name && (
                        <div className="muted">{t.coeur.validatedBy(p.validated_by_name, (p.validated_at ?? "").slice(0, 10))}</div>
                      )}
                      {canValidate && p.status !== "validated" && (
                        <button className="btn btn-sm" onClick={() => void act(() => api.validatePriority(p.id))}>
                          <Check size={13} />
                          {t.coeur.validate}
                        </button>
                      )}
                      {canValidate && p.status === "proposed" && (
                        <button className="btn btn-ghost btn-sm" onClick={() => void act(() => api.rejectPriority(p.id))}>
                          <X size={13} />
                          {t.coeur.reject}
                        </button>
                      )}
                      {!canValidate && p.status === "proposed" && <div className="muted">{t.coeur.reviewerOnly}</div>}
                    </td>
                    <td className="muted">{p.author_name ?? "–"}</td>
                    <td className="muted">{date(p.created_at)}</td>
                    <td className="num">
                      <button
                        className="btn btn-ghost btn-icon"
                        aria-label={`${t.coeur.remove} ${p.title}`}
                        onClick={() => void act(() => api.deletePriority(p.id))}
                      >
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
