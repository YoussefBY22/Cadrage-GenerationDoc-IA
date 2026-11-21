import { Node } from "@tiptap/react";

export interface SentenceOptions {
  /** Appelé au clic sur une référence [n] : reçoit l'identifiant du passage. */
  onSourceClick: (chunkId: string) => void;
}

const STATUS_LABEL: Record<string, string> = {
  verified: "Vérifiée",
  warning: "À vérifier",
  failed: "Échec de vérification",
};

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
        dom.title = STATUS_LABEL[status] ?? "";
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
