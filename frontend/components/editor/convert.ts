import type { SectionDraft, SectionReport, Sentence, SentenceStatus } from "./types";

// Document TipTap minimal : un nœud « sentence » par phrase, dont le contenu est du texte brut.
export interface SentenceAttrs {
  kind: Sentence["kind"];
  sourceLabels: string[];
  sources: string[];
  findings: string[];
  decisions: string[];
  status: SentenceStatus | null;
}

export interface TipTapNode {
  type: string;
  attrs?: Record<string, unknown>;
  content?: TipTapNode[];
  text?: string;
}

export interface TipTapDoc {
  type: "doc";
  content: TipTapNode[];
}

/** Statuts de vérification par index de phrase (absents = null). */
export function statusesOf(report: SectionReport | undefined, count: number): (SentenceStatus | null)[] {
  const out: (SentenceStatus | null)[] = Array(count).fill(null);
  for (const c of report?.report.checks ?? []) if (c.index < count) out[c.index] = c.status;
  return out;
}

export function sectionToDoc(section: SectionDraft, report?: SectionReport): TipTapDoc {
  const statuses = statusesOf(report, section.sentences.length);
  const content: TipTapNode[] = section.sentences.map((s, i) => ({
    type: "sentence",
    attrs: {
      kind: s.kind,
      sourceLabels: s.source_labels,
      sources: s.source_ids,
      findings: s.finding_ids,
      decisions: s.decision_ids ?? [],
      status: statuses[i],
    } satisfies SentenceAttrs,
    // un texte vide n'a pas de nœud texte (ProseMirror l'interdit)
    content: s.text ? [{ type: "text", text: s.text }] : [],
  }));
  // ProseMirror exige au moins un enfant : une section sans phrase reçoit une phrase vide « jetable »
  return { type: "doc", content: content.length ? content : [emptySentence()] };
}

function emptySentence(): TipTapNode {
  return {
    type: "sentence",
    attrs: { kind: "fact", sourceLabels: [], sources: [], findings: [], decisions: [], status: null },
    content: [],
  };
}

const textOf = (n: TipTapNode): string =>
  n.text ?? (n.type === "hardBreak" ? "\n" : (n.content ?? []).map(textOf).join(""));

/** Inverse de sectionToDoc : `base` conserve le statut de section et le motif de refus. */
export function docToSection(base: SectionDraft, doc: TipTapDoc): SectionDraft {
  const sentences: Sentence[] = doc.content
    .filter((n) => n.type === "sentence")
    .map((n) => {
      const a = (n.attrs ?? {}) as Partial<SentenceAttrs>;
      return {
        text: textOf(n),
        kind: a.kind ?? "fact",
        source_labels: a.sourceLabels ?? [],
        source_ids: a.sources ?? [],
        finding_ids: a.findings ?? [],
        // absent = aucune décision citée (le serveur complète par une liste vide)
        ...((a.decisions ?? []).length ? { decision_ids: a.decisions } : {}),
      };
    })
    // une phrase vide n'est pas une phrase (cas de la section vide)
    .filter((s) => s.text.trim() !== "" || s.source_ids.length > 0 || (s.decision_ids ?? []).length > 0);
  return { ...base, sentences };
}

export const STATUS_COLOR: Record<SentenceStatus, string> = {
  verified: "green",
  warning: "orange",
  failed: "red",
};
