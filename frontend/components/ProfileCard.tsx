"use client";

import { ImagePlus, Pencil, Save, X } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui";
import { api } from "@/lib/api";
import type { ProjectProfile } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useGuard } from "@/lib/useGuard";

const jour = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "–");

/** Fiche projet : logo, client, demande du client, dates. Reprise dans l'entrepôt (résumé seulement). */
export default function ProfileCard({ dossierId, onChange }: { dossierId: string; onChange?: (p: ProjectProfile) => void }) {
  const guard = useGuard();
  const [p, setP] = useState<ProjectProfile | null>(null);
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState({ client_name: "", client_request: "", request_summary: "", start_date: "", end_date: "" });
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback(
    (x: ProjectProfile) => {
      setP(x);
      onChange?.(x);
    },
    [onChange],
  );

  useEffect(() => {
    api
      .getProfile(dossierId)
      .then(apply)
      .catch((e) => setError(guard(e)));
  }, [dossierId, guard, apply]);

  const open = () => {
    if (!p) return;
    setForm({
      client_name: p.client_name,
      client_request: p.client_request,
      request_summary: p.request_summary,
      start_date: p.start_date ?? "",
      end_date: p.end_date ?? "",
    });
    setEdit(true);
  };

  const run = async (fn: () => Promise<ProjectProfile>) => {
    setError(null);
    try {
      apply(await fn());
      return true;
    } catch (e) {
      setError(guard(e));
      return false;
    }
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    const ok = await run(() =>
      api.saveProfile(dossierId, {
        client_name: form.client_name.trim() || undefined,
        client_request: form.client_request,
        request_summary: form.request_summary,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
      }),
    );
    if (ok) setEdit(false);
  };

  if (!p) return error ? <Alert>{error}</Alert> : null;

  return (
    <section className="card" data-testid="profile-card" style={{ marginBottom: 20 }}>
      {error && <Alert>{error}</Alert>}
      <div style={{ display: "flex", gap: 18, alignItems: "flex-start" }}>
        <div style={{ width: 88, flex: "none", textAlign: "center" }}>
          {p.logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={p.logo} alt={`${t.projet.logo} ${p.client_name}`} style={{ width: 88, height: 88, objectFit: "contain" }} />
          ) : (
            <div className="empty-art" aria-hidden style={{ width: 88, height: 88 }}>
              <ImagePlus size={28} strokeWidth={1.6} />
            </div>
          )}
          <label className="btn btn-ghost btn-sm" style={{ marginTop: 6 }}>
            {p.logo ? t.projet.logoChange : t.projet.logoAdd}
            <input
              type="file"
              hidden
              accept="image/png,image/jpeg"
              data-testid="logo-input"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void run(() => api.uploadLogo(dossierId, f));
                e.target.value = "";
              }}
            />
          </label>
          {p.logo && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => void run(() => api.saveProfile(dossierId, { clear_logo: true }))}>
              {t.projet.logoRemove}
            </button>
          )}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="card-head">
            <div>
              <h2 style={{ margin: 0 }}>{t.projet.profile}</h2>
              <small className="muted">{t.projet.profileHint}</small>
            </div>
            {!edit && (
              <button type="button" className="btn btn-sm" onClick={open} data-testid="profile-edit">
                <Pencil size={14} />
                {t.projet.edit}
              </button>
            )}
          </div>
          {!edit ? (
            <dl className="kv">
              <dt>{t.projet.client}</dt>
              <dd>{p.client_name}</dd>
              <dt>{t.projet.request}</dt>
              <dd style={{ whiteSpace: "pre-wrap" }}>{p.client_request || <span className="muted">{t.projet.noRequest}</span>}</dd>
              <dt>
                {t.projet.start} – {t.projet.end}
              </dt>
              <dd>
                {jour(p.start_date)} – {jour(p.end_date)}
              </dd>
              <dt>{t.nav.documents}</dt>
              <dd>{t.projet.counts(p.documents, p.audit_reports)}</dd>
            </dl>
          ) : (
            <form onSubmit={save} className="stack" data-testid="profile-form">
              <label>
                <span>{t.projet.client}</span>
                <input value={form.client_name} maxLength={255} onChange={(e) => setForm({ ...form, client_name: e.target.value })} />
              </label>
              <label>
                <span>{t.projet.request}</span>
                <textarea
                  rows={4}
                  value={form.client_request}
                  placeholder={t.projet.requestPlaceholder}
                  onChange={(e) => setForm({ ...form, client_request: e.target.value })}
                />
              </label>
              <label>
                <span>{t.projet.summary}</span>
                <input value={form.request_summary} maxLength={200} onChange={(e) => setForm({ ...form, request_summary: e.target.value })} />
                <small className="muted">{t.projet.summaryHint}</small>
              </label>
              <div className="row" style={{ gap: 12 }}>
                <label>
                  <span>{t.projet.start}</span>
                  <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
                </label>
                <label>
                  <span>{t.projet.end}</span>
                  <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
                </label>
              </div>
              <small className="muted">{t.projet.logoHint}</small>
              <div className="row" style={{ gap: 8 }}>
                <button className="btn btn-primary" type="submit">
                  <Save size={15} />
                  {t.projet.save}
                </button>
                <button className="btn btn-ghost" type="button" onClick={() => setEdit(false)}>
                  <X size={15} />
                  {t.projet.cancel}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </section>
  );
}
