import type {
  AssistantAnswer,
  SearchHit,
  Job,
  DeliverableSummary,
  DocumentDeletePreview,
  DossierDeletePreview,
  ChunkDetail,
  DocumentInfo,
  DocumentRole,
  Coverage,
  Dossier,
  ExistingProject,
  Finding,
  FindingPatch,
  ContextBudget,
  LoginResponse,
  ModelsOverview,
  TestReport,
  Passage,
  Role,
  ChatReply,
  ChatTurn,
  ContextData,
  ContextSheet,
  Decision,
  DecisionCategory,
  Priority,
  ProjectState,
  RoadmapGenerated,
  UploadResult,
  AuditRecommendation,
  ProfilePatch,
  ProjectProfile,
  RecommendationsOverview,
} from "./api-types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PREFIX = "/api/v1";
const TOKEN_KEY = "cadrage.token";
const ROLE_KEY = "cadrage.role";

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
  else {
    s.removeItem(TOKEN_KEY);
    s.removeItem(ROLE_KEY);
  }
}

/** Rôle mémorisé à la connexion (sert seulement à afficher le menu ; le serveur contrôle l'accès). */
export function getRole(): string | null {
  return storage()?.getItem(ROLE_KEY) ?? null;
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
    storage()?.setItem(ROLE_KEY, r.user.role);
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
  uploadDocument(dossierId: string, file: File, role: DocumentRole = "other"): Promise<UploadResult> {
    const form = new FormData();
    form.append("file", file);
    form.append("role", role);
    return request<UploadResult>(`/dossiers/${dossierId}/documents`, {
      method: "POST",
      body: form,
    });
  },
  async documentFile(id: string): Promise<Blob> {
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`${API_URL}${PREFIX}/documents/${id}/file`, { headers });
    if (!res.ok) throw await toError(res);
    return res.blob();
  },
  getDocument: (id: string) => request<DocumentInfo>(`/documents/${id}`),
  documentDeletePreview: (id: string) => request<DocumentDeletePreview>(`/documents/${id}/delete-preview`),
  deleteDocument: (id: string) => request<DocumentDeletePreview>(`/documents/${id}`, { method: "DELETE" }),
  dossierDeletePreview: (id: string) => request<DossierDeletePreview>(`/dossiers/${id}/delete-preview`),
  deleteDossier: (id: string) => request<DossierDeletePreview>(`/dossiers/${id}`, { method: "DELETE" }),
  findingAction: (id: string, action: "unmerge" | "merge" | "restore" | "discard" | "original", body: { target_id?: string; reason?: string } = {}) =>
    request<{ ok: boolean }>(`/findings/${id}:${action}`, json("POST", body)),
  assistant: (dossierId: string | null, body: { message: string; history: { role: string; text: string }[]; page_help?: string }, signal?: AbortSignal) =>
    request<AssistantAnswer>(dossierId ? `/dossiers/${dossierId}/assistant` : "/assistant", { ...json("POST", body), signal }),
  startJob: (dossierId: string, kind: Job["kind"]) => request<Job>(`/dossiers/${dossierId}/jobs`, json("POST", { kind })),
  listJobs: (dossierId: string) => request<Job[]>(`/dossiers/${dossierId}/jobs`),
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  cancelJob: (id: string) => request<Job>(`/jobs/${id}:cancel`, { method: "POST" }),
  busy: () => request<{ label: string; dossier_id: string; done: number; total: number | null }[]>("/jobs/busy"),
  listDeliverables: (dossierId: string) => request<DeliverableSummary[]>(`/dossiers/${dossierId}/deliverables`),
  deleteDeliverable: (id: string) => request<void>(`/deliverables/${id}`, { method: "DELETE" }),
  setDocumentRole: (id: string, role: DocumentRole) =>
    request<DocumentInfo>(`/documents/${id}`, json("PATCH", { role })),
  getContext: (dossierId: string) => request<ContextSheet>(`/dossiers/${dossierId}/context`),
  saveContext: (dossierId: string, body: Partial<ContextData> & { confirm?: boolean }) =>
    request<ContextSheet>(`/dossiers/${dossierId}/context`, json("PUT", body)),
  chat: (dossierId: string, message: string, history: ChatTurn[]) =>
    request<ChatReply>(`/dossiers/${dossierId}/chat`, json("POST", { message, history })),
  listDecisions: (dossierId: string) => request<Decision[]>(`/dossiers/${dossierId}/decisions`),
  createDecision: (dossierId: string, body: { category: DecisionCategory; text: string }) =>
    request<Decision>(`/dossiers/${dossierId}/decisions`, json("POST", body)),
  patchDecision: (id: string, body: { category?: DecisionCategory; text?: string }) =>
    request<Decision>(`/decisions/${id}`, json("PATCH", body)),
  confirmDecision: (id: string) => request<Decision>(`/decisions/${id}:confirm`, { method: "POST" }),
  retractDecision: (id: string) => request<Decision>(`/decisions/${id}:retract`, { method: "POST" }),
  deleteDecision: (id: string) => request<void>(`/decisions/${id}`, { method: "DELETE" }),
  listPriorities: (dossierId: string) => request<Priority[]>(`/dossiers/${dossierId}/priorities`),
  createPriority: (dossierId: string, body: { title: string; description?: string }) =>
    request<Priority>(`/dossiers/${dossierId}/priorities`, json("POST", body)),
  patchPriority: (id: string, body: Partial<Pick<Priority, "title" | "description" | "rank">> & { status?: "proposed" }) =>
    request<Priority>(`/priorities/${id}`, json("PATCH", body)),
  validatePriority: (id: string) => request<Priority>(`/priorities/${id}:validate`, { method: "POST" }),
  rejectPriority: (id: string) => request<Priority>(`/priorities/${id}:reject`, { method: "POST" }),
  deletePriority: (id: string) => request<void>(`/priorities/${id}`, { method: "DELETE" }),
  listProjects: (dossierId: string) => request<ExistingProject[]>(`/dossiers/${dossierId}/projects`),
  createProject: (
    dossierId: string,
    body: { title: string; state?: ProjectState; duration_weeks?: number | null; depends_on?: string[] },
  ) => request<ExistingProject>(`/dossiers/${dossierId}/projects`, json("POST", body)),
  patchProject: (
    id: string,
    body: { title?: string; state?: ProjectState; duration_weeks?: number | null; depends_on?: string[] },
  ) => request<ExistingProject>(`/projects/${id}`, json("PATCH", body)),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  getChunk: (id: string) => request<ChunkDetail>(`/chunks/${id}`),
  search: (dossierId: string, texts: string[], k = 10, mode: "meaning" | "words" = "meaning") =>
    request<SearchHit[]>(`/dossiers/${dossierId}/search`, json("POST", { texts, k, mode })),
  listFindings: (dossierId: string) => request<Finding[]>(`/dossiers/${dossierId}/findings`),
  extractFindings: (dossierId: string) =>
    request<{ coverage?: Coverage }>(`/dossiers/${dossierId}/findings:extract`, { method: "POST" }),
  me: () => request<{ id: string; role: Role }>("/auth/me"),
  patchFinding: (id: string, patch: FindingPatch) =>
    request<Finding>(`/findings/${id}`, json("PATCH", patch)),
  generateRoadmap: (dossierId: string) =>
    request<RoadmapGenerated>(`/dossiers/${dossierId}/roadmap:generate`, json("POST", {})),
  createDeliverable: (dossierId: string, type: "tor" | "cdc", initiative_id?: string) =>
    request<{ deliverable_id: string }>(`/dossiers/${dossierId}/deliverables`, json("POST", { type, initiative_id })),
  listModels: () => request<ModelsOverview>("/admin/models"),
  contextBudget: (candidateTokens: number) =>
    request<ContextBudget>(`/admin/models/context?candidate_tokens=${candidateTokens}`),
  testModel: (model: string) => request<TestReport>("/admin/models/test", json("POST", { model })),
  activateModel: (model: string) =>
    request<{ active: string }>("/admin/models/activate", json("POST", { model })),
  getProfile: (dossierId: string) => request<ProjectProfile>(`/dossiers/${dossierId}/profile`),
  saveProfile: (dossierId: string, body: ProfilePatch) =>
    request<ProjectProfile>(`/dossiers/${dossierId}/profile`, json("PUT", body)),
  uploadLogo(dossierId: string, file: File): Promise<ProjectProfile> {
    const form = new FormData();
    form.append("file", file);
    return request<ProjectProfile>(`/dossiers/${dossierId}/profile/logo`, { method: "POST", body: form });
  },
  listRecommendations: (dossierId: string) =>
    request<RecommendationsOverview>(`/dossiers/${dossierId}/recommendations`),
  extractRecommendations: (dossierId: string) =>
    request<RecommendationsOverview>(`/dossiers/${dossierId}/recommendations:extract`, { method: "POST" }),
  addRecommendation: (
    dossierId: string,
    body: { document_id: string; title: string; number?: number | null; page?: number | null },
  ) => request<AuditRecommendation>(`/dossiers/${dossierId}/recommendations`, json("POST", body)),
  patchRecommendation: (
    id: string,
    body: { title?: string; number?: number | null; page?: number | null; status?: "validated" | "proposed" | "deleted"; merge_into?: string },
  ) => request<AuditRecommendation>(`/recommendations/${id}`, json("PATCH", body)),
  setNoRecommendation: (dossierId: string, documentId: string, value: boolean) =>
    request<RecommendationsOverview>(
      `/dossiers/${dossierId}/reports/${documentId}/no-recommendation`,
      json("PUT", { value }),
    ),
  rollbackModel: () => request<{ active: string }>("/admin/models/rollback", { method: "POST" }),
};
