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

export type DecisionCategory = "budget" | "profile" | "schedule" | "duration" | "criterion" | "constraint" | "other";
export type DecisionStatus = "proposed" | "confirmed";

export interface Decision {
  id: string;
  dossier_id: string;
  category: DecisionCategory;
  text: string;
  status: DecisionStatus;
  author_id: string | null;
  author_name?: string | null;
  confirmed_by?: string | null;
  confirmed_by_name?: string | null;
  confirmed_at?: string | null;
  created_at: string | null;
}

export type ProjectType = "software" | "data_ai" | "infrastructure" | "supplies" | "services" | "study" | "change" | "training";

export interface ContextData {
  sector: string;
  size: string;
  country: string;
  language: string;
  project_types: ProjectType[];
  scope: string;
  constraints: string;
  stakeholders: string;
  roadmap_axes: string;
}

export interface ContextSheet {
  dossier_id: string;
  data: ContextData;
  confirmed: boolean;
  confirmed_at: string | null;
  confirmed_by_name?: string | null;
  missing: string[];
  flags: string[];
}

export interface ChatTurn {
  role: "user" | "assistant";
  text: string;
}

export interface ChatReply {
  status: "ok" | "refused" | "invalid";
  reason?: string | null;
  reply: string;
  questions: string[];
  proposals: {
    fields: { field: keyof ContextData; value: string | ProjectType[]; current: string | ProjectType[] }[];
    decisions: { category: DecisionCategory; label: string; text: string }[];
  };
  dropped: { kind: string; value: string; why: string }[];
  sent: { passages: number; history_turns: number; history_dropped: number };
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
  /** Document, page et rang de chaque source (liste uniquement). */
  sources?: SourceRef[];
}

export interface SourceRef {
  chunk_id: string;
  document_id: string;
  filename: string;
  page_start: number | null;
  page_end: number | null;
  ordinal: number;
  document_rank: number;
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

// --- Fiche projet et recommandations des rapports d'audit --------------------------------------
export interface ProjectProfile {
  dossier_id: string;
  name: string;
  client_name: string;
  client_request: string;
  request_summary: string;
  start_date: string | null;
  end_date: string | null;
  logo: string | null;
  documents: number;
  audit_reports: number;
  updated_at: string | null;
}

export type ProfilePatch = Partial<
  Pick<ProjectProfile, "client_name" | "client_request" | "request_summary" | "start_date" | "end_date">
> & { clear_logo?: boolean };

export type RecommendationStatus = "proposed" | "validated" | "deleted" | "merged";

export interface AuditRecommendation {
  id: string;
  document_id: string;
  number: number | null;
  page: number | null;
  title: string;
  status: RecommendationStatus;
  origin: "rules" | "consultant";
  merged_into: string | null;
}

export type ReportCheckStatus = "ok" | "ecart" | "non_detectees" | "non_lu";

export interface ReportRecommendations {
  document_id: string;
  filename: string;
  pages: number | null;
  recommendations: AuditRecommendation[];
  check: { status: ReportCheckStatus; expected: number | null; extracted: number; missing: number[]; duplicates: number[] };
}

export interface RecommendationsOverview {
  reports: ReportRecommendations[];
  alerts: number;
  validated: number;
  active: number;
}

export interface DocumentDeletePreview {
  passages: number;
  findings: number;
  findings_partial: number;
  recommendations: number;
}

export interface DossierDeletePreview {
  documents: number;
  findings: number;
  deliverables: number;
  recommendations: number;
  decisions: number;
}

export interface DeliverableSummary {
  id: string;
  type: "roadmap" | "tor" | "cdc";
  state: string;
  version: number;
  created_at: string | null;
  updated_at: string | null;
}
