"use client";

import { Check, ChevronRight, Gavel, Plus, Trash2, Undo2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { Decision, DecisionCategory } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useDossier } from "@/lib/useDossier";
import { useGuard } from "@/lib/useGuard";

const CATEGORIES: DecisionCategory[] = ["budget", "profile", "schedule", "duration", "criterion", "constraint", "other"];
const date = (iso: string | null | undefined) => (iso ? iso.slice(0, 10) : "–");

/** Décisions humaines : budget, profils, calendrier… Seules les confirmées servent à générer. */
export default function DecisionsView({ dossierId }: { dossierId: string }) {
  const guard = useGuard();
  const dossier = useDossier(dossierId);
  const [items, setItems] = useState<Decision[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<DecisionCategory>("profile");
  const [text, setText] = useState("");

  const load = useCallback(() => {
    api
      .listDecisions(dossierId)
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

  const save = (status: "proposed" | "confirmed") => {
    if (!text.trim()) return;
    void act(async () => {
      // La création ne confirme jamais : « confirmer » est un second appel, audité à part.
      const made = await api.createDecision(dossierId, { category, text: text.trim() });
      if (status === "confirmed") await api.confirmDecision(made.id);
      setText("");
    });
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save("proposed");
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
          <h1>{t.decisions.title}</h1>
          <small className="muted">{t.decisions.hint}</small>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}

      <form className="card form-row" onSubmit={submit} data-testid="decision-form">
        <label>
          <span>{t.decisions.category}</span>
          <select value={category} onChange={(e) => setCategory(e.target.value as DecisionCategory)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t.decisions.categories[c]}
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          <span>{t.decisions.text}</span>
          <input value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} required />
        </label>
        <button className="btn" type="submit">
          <Plus size={16} />
          {t.decisions.add}
        </button>
        <button className="btn btn-primary" type="button" onClick={() => save("confirmed")}>
          <Check size={16} />
          {t.decisions.addConfirm}
        </button>
      </form>

      <div style={{ marginTop: 20 }}>
        {items === null && !error && <p className="muted">{t.common.loading}</p>}
        {items?.length === 0 && <Empty icon={Gavel} label={t.decisions.empty} />}
        {items && items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.decisions.category}</th>
                  <th>{t.decisions.text}</th>
                  <th>{t.coeur.statusField}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((d) => (
                  <tr key={d.id} data-testid={`decision-${d.id}`}>
                    <td>{t.decisions.categories[d.category]}</td>
                    <td style={{ minWidth: 140, whiteSpace: "normal" }}>{d.text}</td>
                    <td>
                      <span className={`badge ${d.status === "confirmed" ? "approved" : "draft"}`}>
                        {t.decisions.status[d.status]}
                      </span>
                      {d.status === "confirmed" && (
                        <div className="muted" style={{ whiteSpace: "normal", maxWidth: 190 }}>{t.decisions.by(d.author_name ?? "–", date(d.confirmed_at))}</div>
                      )}
                    </td>
                    <td className="num">
                      {d.status === "proposed" ? (
                        <button className="btn btn-sm" onClick={() => void act(() => api.confirmDecision(d.id))}>
                          <Check size={13} />
                          {t.decisions.confirm}
                        </button>
                      ) : (
                        <button
                          className="btn btn-ghost btn-icon"
                          aria-label={`${t.decisions.retract} ${d.text}`}
                          title={t.decisions.retract}
                          onClick={() => void act(() => api.retractDecision(d.id))}
                        >
                          <Undo2 size={15} />
                        </button>
                      )}
                      <button
                        className="btn btn-ghost btn-icon"
                        aria-label={`${t.decisions.remove} ${d.text}`}
                        onClick={() => void act(() => api.deleteDecision(d.id))}
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
