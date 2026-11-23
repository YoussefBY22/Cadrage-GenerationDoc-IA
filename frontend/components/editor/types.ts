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
  decision_ids?: string[];
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
  objective?: string;
  expected_result?: string;
  indicator?: string;
  priority_ids?: string[];
  depends_on_projects?: string[];
  proposal_status?: "proposed" | "accepted";
  proposal_flags?: string[];
}

export interface RejectedLink {
  initiative: string;
  kind: string;
  value: string;
}

export type CoherenceSeverity = "blocking" | "warning" | "info";

export interface CoherenceIssue {
  code: string;
  severity: CoherenceSeverity;
  refs: Record<string, unknown>;
}

export interface ChainLink {
  id: string;
  title: string;
  source_ids: string[];
  kind: string;
  extra: Record<string, unknown>;
}

export interface Chain {
  initiative_id: string;
  title: string;
  objective: string;
  expected_result: string;
  indicator: string;
  proposal_status: "proposed" | "accepted";
  proposal_flags: string[];
  findings: ChainLink[];
  priorities: ChainLink[];
  dependencies: ChainLink[];
  source_ids: string[];
  rank: number;
  wave: number;
  inherited_rank: number | null;
  position: number;
  start_week: number | null;
  end_week: number | null;
  issues: string[];
}

export interface Coherence {
  issues: CoherenceIssue[];
  chains: Chain[];
  sequence: { initiative_id: string; position: number; start_week: number | null; end_week: number | null }[];
}

export interface ScoredInitiative {
  initiative: Initiative;
  score: number;
  rank: number;
  wave: number;
  unscored?: string[];
}

export interface RoadmapResult {
  criteria: Criterion[];
  items: ScoredInitiative[];
  topo_order: string[];
  cycles: string[][];
  critical_path: string[];
  rejected_links?: RejectedLink[];
  passages_not_sent?: number;
}

export interface DeliverableContent {
  type: "tor" | "cdc" | "roadmap" | "findings";
  language: "fr" | "en";
  template_id: string;
  template_version: string;
  sections: SectionDraft[];
  roadmap: RoadmapResult | null;
  modules?: string[];
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
  modules?: string[];
  /** Sections du gabarit exact (tronc commun + modules) et décisions humaines exigées. */
  sections?: { key: string; title: string; requires_decisions: string[]; requires_labels: string[] }[];
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
