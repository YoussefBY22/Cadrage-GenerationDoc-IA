// Types du livrable (docs/06 §3, §6, §8), écrits à la main.

export type SentenceKind = "fact" | "recommendation" | "transition";
export type SentenceStatus = "verified" | "warning" | "failed";
export type DeliverableState = "draft" | "in_review" | "approved" | "rejected";
export type Role = "consultant" | "reviewer" | "admin";

export interface Sentence {
  text: string;
  kind: SentenceKind;
  source_labels: string[];
  source_ids: string[];
  finding_ids: string[];
}

export interface SectionDraft {
  section_key: string;
  status: "ok" | "insufficient_evidence";
  sentences: Sentence[];
  missing_evidence: string | null;
}

export interface Criterion {
  key: string;
  label: string;
  weight: number;
  higher_is_better: boolean;
}

export interface CriterionScore {
  key: string;
  value: number;
  source_ids: string[];
  rationale: string;
}

export interface Initiative {
  id: string;
  title: string;
  description: string;
  finding_ids: string[];
  scores: CriterionScore[];
  depends_on: string[];
  duration_weeks: number | null;
}

export interface ScoredInitiative {
  initiative: Initiative;
  score: number;
  rank: number;
  wave: number;
}

export interface RoadmapResult {
  criteria: Criterion[];
  items: ScoredInitiative[];
  topo_order: string[];
  cycles: string[][];
  critical_path: string[];
}

export interface DeliverableContent {
  type: "tor" | "cdc" | "roadmap" | "findings";
  language: "fr" | "en";
  template_id: string;
  template_version: string;
  sections: SectionDraft[];
  roadmap: RoadmapResult | null;
}

export interface SentenceCheck {
  index: number;
  status: SentenceStatus;
  numbers_cited: number;
  numbers_found: number;
  support: number;
}

export interface Issue {
  sentence_index: number;
  code: string;
  severity: "blocking" | "warning";
  detail: string;
}

export interface SectionReport {
  report: { section_key: string; checks: SentenceCheck[]; issues: Issue[] };
  tpv: number;
}

export interface Deliverable {
  id: string;
  dossier_id: string;
  type: DeliverableContent["type"];
  state: DeliverableState;
  template_id: string;
  version: number;
  content: DeliverableContent;
  reports: SectionReport[];
}

export interface VersionInfo {
  version: number;
  origin: "generated" | "edited" | "restored";
  author_id: string | null;
  created_at: string | null;
  content_sha256: string;
}

export interface SectionDiff {
  section_key: string;
  status: "added" | "removed" | "changed" | "unchanged";
  sentences: { op: string; old: string[]; new: string[] }[];
}

export interface CommentInfo {
  id: string;
  section_key: string;
  user_id: string;
  text: string;
  created_at: string | null;
}

export const TEMPLATE_SECTIONS: Record<string, { key: string; title: string }[]> = {
  tor: [
    { key: "contexte", title: "Contexte" },
    { key: "objectifs", title: "Objectifs" },
    { key: "livrables", title: "Livrables attendus" },
    { key: "calendrier", title: "Calendrier" },
    { key: "profil", title: "Profil recherché" },
    { key: "evaluation", title: "Critères d'évaluation" },
  ],
  cdc: [
    { key: "perimetre", title: "Périmètre" },
    { key: "fonctionnelles", title: "Exigences fonctionnelles" },
    { key: "non_fonctionnelles", title: "Exigences non fonctionnelles" },
    { key: "contraintes", title: "Contraintes" },
    { key: "recette", title: "Recette" },
  ],
  roadmap: [
    { key: "synthese", title: "Synthèse" },
    { key: "axes", title: "Axes" },
    { key: "initiatives", title: "Initiatives" },
    { key: "calendrier", title: "Calendrier" },
    { key: "risques", title: "Risques" },
  ],
  findings: [{ key: "constats", title: "Constats" }],
};
