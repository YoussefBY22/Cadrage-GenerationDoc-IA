"use client";

import { ChevronRight, FolderKanban, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert, Empty } from "@/components/ui";
import { api } from "@/lib/api";
import type { ExistingProject, ProjectState } from "@/lib/api-types";
import { t } from "@/lib/i18n";
import { useGuard } from "@/lib/useGuard";

const STATES: ProjectState[] = ["existing", "in_progress", "planned", "done"];

/** Projets existants : état, durée facultative, dépendances entre projets. */
export default function ProjectsView({ dossierId }: { dossierId: string }) {
  const guard = useGuard();
  const [items, setItems] = useState<ExistingProject[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [state, setState] = useState<ProjectState>("existing");
  const [duration, setDuration] = useState("");

  const load = useCallback(() => {
    api
      .listProjects(dossierId)
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
      await api.createProject(dossierId, {
        title: title.trim(),
        state,
        duration_weeks: duration ? Number(duration) : null,
      });
      setTitle("");
      setDuration("");
    });
  };

  const name = (id: string) => items?.find((p) => p.id === id)?.title ?? id;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link href={`/dossiers/${dossierId}`}>{t.nav.dossiers}</Link>
            <ChevronRight size={14} />
          </div>
          <h1>{t.coeur.projects}</h1>
          <small className="muted">{t.coeur.projectsHint}</small>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}

      <form className="card form-row" onSubmit={add} data-testid="project-form">
        <label className="grow">
          <span>{t.coeur.titleField}</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={500} required />
        </label>
        <label>
          <span>{t.coeur.stateField}</span>
          <select value={state} onChange={(e) => setState(e.target.value as ProjectState)}>
            {STATES.map((s) => (
              <option key={s} value={s}>
                {t.coeur.projectState[s]}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t.coeur.durationField}</span>
          <input
            type="number"
            min={1}
            max={520}
            className="mini-input"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
          />
        </label>
        <button className="btn btn-primary" type="submit">
          <Plus size={16} />
          {t.coeur.add}
        </button>
      </form>

      <div style={{ marginTop: 20 }}>
        {items === null && !error && <p className="muted">{t.common.loading}</p>}
        {items?.length === 0 && <Empty icon={FolderKanban} label={t.coeur.noProjects} />}
        {items && items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.coeur.titleField}</th>
                  <th>{t.coeur.stateField}</th>
                  <th>{t.coeur.durationField}</th>
                  <th>{t.coeur.dependsField}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((p) => (
                  <tr key={p.id} data-testid={`project-${p.id}`}>
                    <td style={{ minWidth: 200 }}>
                      <b>{p.title}</b>
                    </td>
                    <td>
                      <select
                        className="mini-select"
                        value={p.state}
                        aria-label={`${p.title} ${t.coeur.stateField}`}
                        onChange={(e) =>
                          void act(() => api.patchProject(p.id, { state: e.target.value as ProjectState }))
                        }
                      >
                        {STATES.map((s) => (
                          <option key={s} value={s}>
                            {t.coeur.projectState[s]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input
                        type="number"
                        min={1}
                        max={520}
                        className="mini-input"
                        aria-label={`${p.title} ${t.coeur.durationField}`}
                        defaultValue={p.duration_weeks ?? ""}
                        key={`${p.id}-${p.duration_weeks}`}
                        onBlur={(e) => {
                          const n = e.target.value ? Number(e.target.value) : null;
                          if (n !== p.duration_weeks) void act(() => api.patchProject(p.id, { duration_weeks: n }));
                        }}
                      />
                    </td>
                    <td>
                      <details className="picker">
                        <summary>{p.depends_on.length ? p.depends_on.map(name).join(", ") : "–"}</summary>
                        {items
                          .filter((o) => o.id !== p.id)
                          .map((o) => (
                            <label key={o.id}>
                              <input
                                type="checkbox"
                                checked={p.depends_on.includes(o.id)}
                                onChange={(e) =>
                                  void act(() =>
                                    api.patchProject(p.id, {
                                      depends_on: e.target.checked
                                        ? [...p.depends_on, o.id]
                                        : p.depends_on.filter((d) => d !== o.id),
                                    }),
                                  )
                                }
                              />
                              {o.title}
                            </label>
                          ))}
                      </details>
                    </td>
                    <td className="num">
                      <button
                        className="btn btn-ghost btn-icon"
                        aria-label={`${t.coeur.remove} ${p.title}`}
                        onClick={() => void act(() => api.deleteProject(p.id))}
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
