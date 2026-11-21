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
