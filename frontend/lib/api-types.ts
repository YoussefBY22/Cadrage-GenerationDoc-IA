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
