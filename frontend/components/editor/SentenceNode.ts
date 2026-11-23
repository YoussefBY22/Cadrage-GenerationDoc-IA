import { Node } from "@tiptap/react";
import { m } from "./i18n";

export interface SentenceOptions {
  /** Appelé au clic sur une référence [n] : reçoit l'identifiant du passage. */
  onSourceClick: (chunkId: string) => void;
}


/** Nœud « phrase » : texte brut + attributs (statut, sources). Les sources se lisent via [n]. */
export const SentenceNode = Node.create<SentenceOptions>({
  name: "sentence",
  group: "block",
  content: "inline*",
  defining: true,

  addOptions() {
    return { onSourceClick: () => {} };
  },

  addAttributes() {
    return {
      kind: { default: "fact" },
      sourceLabels: { default: [] },
      sources: { default: [] },
      findings: { default: [] },
      decisions: { default: [] },
      status: { default: null },
    };
  },

  parseHTML() {
    return [{ tag: "div[data-sentence]" }];
  },

  renderHTML({ node }) {
    return ["div", { "data-sentence": "", "data-status": node.attrs.status ?? "none" }, 0];
  },

  addNodeView() {
    const onClick = this.options.onSourceClick;
    return ({ node: initial }) => {
      let node = initial;
      const dom = document.createElement("div");
      dom.setAttribute("data-sentence", "");
      const content = document.createElement("p");
      content.className = "sentence-text";
      const refs = document.createElement("span");
      refs.contentEditable = "false";
      refs.className = "sentence-refs";
      dom.append(content, refs);

      const paint = () => {
        const status = (node.attrs.status as string | null) ?? "none";
        dom.setAttribute("data-status", status);
        dom.title = m.statusLabel[status] ?? "";
        refs.replaceChildren();
        (node.attrs.sources as string[]).forEach((id, i) => {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "link";
          b.textContent = `[${i + 1}]`; // textContent : jamais de HTML interprété
          b.setAttribute("data-source", id);
          b.addEventListener("click", () => onClick(id));
          refs.append(b);
        });
        ((node.attrs.decisions as string[] | undefined) ?? []).forEach((id) => {
          const tag = document.createElement("span");
          tag.className = "tag";
          tag.textContent = "D"; // décision humaine citée ; le détail est dans l'écran Décisions
          tag.title = m.decisionCited;
          tag.setAttribute("data-decision", id);
          refs.append(tag);
        });
      };
      paint();
      return {
        dom,
        contentDOM: content,
        update(updated) {
          if (updated.type !== node.type) return false;
          node = updated;
          paint();
          return true;
        },
        ignoreMutation: (m: MutationRecord | { type: "selection" }) =>
          m.type !== "selection" && refs.contains((m as MutationRecord).target),
      };
    };
  },
});
