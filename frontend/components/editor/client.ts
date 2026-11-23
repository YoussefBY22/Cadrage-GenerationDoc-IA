import { API_URL, ApiError, getToken, setToken } from "@/lib/api";
import type {
  CommentInfo,
  Deliverable,
  DeliverableContent,
  DeliverableState,
  Role,
  SectionDiff,
  VersionInfo,
} from "./types";

const PREFIX = "/api/v1";

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  const res = await fetch(API_URL + PREFIX + path, { ...init, headers });
  if (!res.ok) {
    if (res.status === 401) setToken(null);
    let code = "HTTP_" + res.status;
    let message = res.statusText || "Erreur";
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? (typeof body?.detail === "string" ? body.detail : message);
    } catch {
      /* corps non JSON */
    }
    throw new ApiError(res.status, code, message);
  }
  return res;
}

const call = async <T>(path: string, init?: RequestInit): Promise<T> =>
  (await raw(path, init)).json() as Promise<T>;

const body = (method: string, data: unknown): RequestInit => ({ method, body: JSON.stringify(data) });

export type ExportFormat = "docx" | "pptx" | "pdf";

export const deliverables = {
  me: () => call<{ id: string; role: Role }>("/auth/me"),
  get: (id: string) => call<Deliverable>(`/deliverables/${id}`),
  versions: (id: string) => call<VersionInfo[]>(`/deliverables/${id}/versions`),
  saveContent: (id: string, content: DeliverableContent) =>
    call<{ version: number }>(`/deliverables/${id}/content`, body("PUT", content)),
  restore: (id: string, n: number) =>
    call<{ version: number }>(`/deliverables/${id}/versions/${n}:restore`, { method: "POST" }),
  diff: (id: string, from: number, to: number) =>
    call<{ sections: SectionDiff[] }>(`/deliverables/${id}/diff?from=${from}&to=${to}`),
  comments: (id: string) => call<CommentInfo[]>(`/deliverables/${id}/comments`),
  addComment: (id: string, key: string, text: string) =>
    call<{ id: string }>(`/deliverables/${id}/sections/${key}/comments`, body("POST", { text })),
  transition: (id: string, to: DeliverableState, reason?: string) =>
    call<{ state: DeliverableState }>(`/deliverables/${id}/transitions`, body("POST", { to, reason })),
  acknowledge: (id: string, section_key: string, sentence_index: number, reason: string) =>
    call<unknown>(`/deliverables/${id}/acknowledgements`, body("POST", { section_key, sentence_index, reason })),
  generateSection: (id: string, key: string) =>
    call<{ version: number }>(`/deliverables/${id}/sections/${key}:generate`, { method: "POST" }),
  patchRoadmap: (
    id: string,
    initiatives: {
      id: string;
      scores?: { key: string; value: number }[];
      duration_weeks?: number;
      depends_on?: string[];
    }[],
  ) => call<unknown>(`/deliverables/${id}/roadmap`, body("PATCH", { initiatives })),
  async exportFile(id: string, format: ExportFormat): Promise<{ blob: Blob; filename: string }> {
    const res = await raw(`/deliverables/${id}/exports`, body("POST", { format }));
    const cd = res.headers.get("Content-Disposition") ?? "";
    const name = /filename="?([^";]+)"?/.exec(cd)?.[1] ?? `livrable.${format}`;
    return { blob: await res.blob(), filename: name };
  },
};
