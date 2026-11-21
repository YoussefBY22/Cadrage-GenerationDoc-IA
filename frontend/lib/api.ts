import type {
  ChunkDetail,
  DocumentInfo,
  Dossier,
  Finding,
  FindingPatch,
  LoginResponse,
  Passage,
  UploadResult,
} from "./api-types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PREFIX = "/api/v1";
const TOKEN_KEY = "cadrage.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// Jeton : en mémoire, doublé dans sessionStorage (survit au rechargement, pas à la fermeture).
let memoryToken: string | null = null;

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  if (memoryToken) return memoryToken;
  memoryToken = storage()?.getItem(TOKEN_KEY) ?? null;
  return memoryToken;
}

export function setToken(token: string | null): void {
  memoryToken = token;
  const s = storage();
  if (!s) return;
  if (token) s.setItem(TOKEN_KEY, token);
  else s.removeItem(TOKEN_KEY);
}

async function toError(res: Response): Promise<ApiError> {
  let code = "HTTP_" + res.status;
  let message = res.statusText || "Erreur";
  try {
    const body = await res.json();
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    } else if (typeof body?.detail === "string") {
      message = body.detail;
    }
  } catch {
    /* corps non JSON : valeurs par défaut */
  }
  return new ApiError(res.status, code, message);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  const res = await fetch(API_URL + PREFIX + path, { ...init, headers });
  if (!res.ok) {
    if (res.status === 401) setToken(null);
    throw await toError(res);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

export const api = {
  async login(email: string, password: string): Promise<LoginResponse> {
    const r = await request<LoginResponse>("/auth/login", json("POST", { email, password }));
    setToken(r.token);
    return r;
  },
  async logout(): Promise<void> {
    try {
      await request<void>("/auth/logout", { method: "POST" });
    } finally {
      setToken(null);
    }
  },
  listDossiers: () => request<Dossier[]>("/dossiers"),
  getDossier: (id: string) => request<Dossier>(`/dossiers/${id}`),
  createDossier: (name: string, client_name: string, language: "fr" | "en" = "fr") =>
    request<Dossier>("/dossiers", json("POST", { name, client_name, language })),
  listDocuments: (dossierId: string) =>
    request<DocumentInfo[]>(`/dossiers/${dossierId}/documents`),
  uploadDocument(dossierId: string, file: File): Promise<UploadResult> {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResult>(`/dossiers/${dossierId}/documents`, {
      method: "POST",
      body: form,
    });
  },
  getChunk: (id: string) => request<ChunkDetail>(`/chunks/${id}`),
  search: (dossierId: string, texts: string[], k = 10) =>
    request<Passage[]>(`/dossiers/${dossierId}/search`, json("POST", { texts, k })),
  listFindings: (dossierId: string) => request<Finding[]>(`/dossiers/${dossierId}/findings`),
  extractFindings: (dossierId: string) =>
    request<unknown>(`/dossiers/${dossierId}/findings:extract`, { method: "POST" }),
  patchFinding: (id: string, patch: FindingPatch) =>
    request<Finding>(`/findings/${id}`, json("PATCH", patch)),
};
