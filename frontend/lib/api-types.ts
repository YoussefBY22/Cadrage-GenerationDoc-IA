// Types écrits à la main depuis docs/06 §3 et §6 (pas de génération de code).

export type Severity = "low" | "medium" | "high";
export type Role = "consultant" | "reviewer" | "admin";

export interface User {
  id: string;
  role: Role;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface Dossier {
  id: string;
  name: string;
  client_name: string;
  language: "fr" | "en";
  created_at: string | null;
}

export type DocumentRole = "diagnostic" | "strategy" | "portfolio" | "template" | "other";
export type PriorityStatus = "proposed" | "validated" | "rejected";
export type ProjectState = "existing" | "in_progress" | "planned" | "done";

export interface Priority {
  id: string;
  dossier_id: string;
  title: string;
  description: string;
  rank: number;
  status: PriorityStatus;
  source_ids: string[];
  author_id: string | null;
  author_name?: string | null;
  validated_by?: string | null;
  validated_by_name?: string | null;
  validated_at?: string | null;
  created_at: string | null;
}

export interface Coverage {
  documents: number;
  chunks_read: number;
  chunks_failed: number;
  chunks_total: number;
  excluded: { document_id: string; filename: string; role: string; reason: string }[];
}

export interface ExistingProject {
  id: string;
  dossier_id: string;
  title: string;
  state: ProjectState;
  duration_weeks: number | null;
  depends_on: string[];
  source_ids: string[];
  author_id: string | null;
  author_name?: string | null;
  created_at: string | null;
}

export interface DocumentInfo {
  id: string;
  dossier_id: string;
  filename: string;
  mime: string;
  sha256: string;
  title: string | null;
  language: string | null;
  pages: number | null;
  created_at: string | null;
  role: DocumentRole;
}

export interface UploadResult {
  document_id: string;
  chunks: number;
  alerts: number;
}

export interface ChunkDetail {
  id: string;
  dossier_id: string;
  document_id: string;
  document: string;
  text: string;
  page_start: number | null;
  page_end: number | null;
  section_path: string[];
  injection_flags: string[];
}

export interface Chunk {
  id: string;
  document_id: string;
  dossier_id: string;
  ordinal: number;
  text: string;
  page_start: number | null;
  page_end: number | null;
  section_path: string[];
  token_estimate: number;
  injection_flags: string[];
}

export interface Passage {
  label: string;
  chunk: Chunk;
  score: number;
  ranks: Record<string, number>;
}

export interface Finding {
  id: string;
  dossier_id: string;
  text: string;
  theme: string;
  severity: Severity;
  source_ids: string[];
  validated: boolean;
}

export interface FindingPatch {
  text?: string;
  validated?: boolean;
}

export interface RoadmapGenerated {
  deliverable_id: string;
  /** Initiatives classées ; la première (rang 1) sert de contexte au ToR. */
  roadmap: { items: { rank: number; initiative: { id: string } }[] };
}

// --- Modèles de langage (administrateur) : docs/api-modeles.md ---------------------------------

/** Répartition de la fenêtre de contexte pour une section (jetons, estimés). Les quatre parts + `free` = `window_allocated`. */
export interface ContextBudget {
  unit: "tokens";
  estimated: boolean;
  /** Ce que le moteur alloue réellement. */
  window_allocated: number;
  /** Ce que le modèle sait gérer en théorie (null si inconnu). */
  window_max: number | null;
  system: number;
  context: number;
  passages: number;
  response_reserved: number;
  free: number;
  /** Passages retrouvés qui ne tiennent pas : hors fenêtre, jamais envoyés. */
  passages_unsent: number;
  passages_unsent_count: number;
}

export type CheckStatus = "pass" | "warn" | "fail";

export interface TestCheck {
  key: string;
  label: string;
  status: CheckStatus;
  detail: string;
}

export interface TestReport {
  model: string;
  passed: boolean;
  checks: TestCheck[];
  tokens_per_second: number | null;
  num_ctx: number;
  at: string;
}

export interface ModelCard {
  name: string;
  digest: string;
  size_bytes: number | null;
  family: string | null;
  parameter_size: string | null;
  quantization: string | null;
  max_context: number | null;
  /** null : moteur trop ancien pour indiquer les capacités. */
  capabilities: string[] | null;
  license: string | null;
  active: boolean;
  role: "generation" | "embedding";
  test: (Omit<TestReport, "model" | "num_ctx"> & { up_to_date: boolean }) | null;
}

export interface Limits {
  model: { max_context: number | null; vision: boolean | null; capabilities: string[] | null };
  engine: {
    allocated_context: number;
    allocated_source: "config" | "default";
    loaded_context: number | null;
    vram_bytes: number | null;
    gpu_layers: number | null;
    keep_alive: string;
  };
  app: {
    response_reserved: number;
    max_upload_mb: number;
    formats: string[];
    images_used: boolean;
    saturation: string[];
  };
}

export interface HistoryEntry {
  at: string;
  by: string | null;
  action: "initial" | "activate" | "rollback";
  model: string;
}

export interface ModelsOverview {
  engine: { reachable: boolean; provider: string; /** fournisseur fake ou demo : aucun modèle de langage utilisé. */ demo: boolean };
  active: string | null;
  configured: string | null;
  embedding_model: string | null;
  previous: string | null;
  models: ModelCard[];
  history: HistoryEntry[];
  limits: Limits;
  context: ContextBudget;
}
