"use client";

import { Document } from "@tiptap/extension-document";
import { Text } from "@tiptap/extension-text";
import { Dropcursor, UndoRedo } from "@tiptap/extensions";
import { EditorContent, useEditor } from "@tiptap/react";
import { useEffect, useMemo } from "react";
import { docToSection, sectionToDoc, type TipTapDoc } from "./convert";
import { SentenceNode } from "./SentenceNode";
import "./editor.css";
import { m } from "./i18n";
import type { SectionDraft, SectionReport } from "./types";

interface Props {
  section: SectionDraft;
  report?: SectionReport;
  editable: boolean;
  onChange: (section: SectionDraft) => void;
  onSourceClick: (chunkId: string) => void;
}

/** Un éditeur par section : phrases colorées selon leur statut de vérification, TPV affiché. */
export default function SectionEditor({ section, report, editable, onChange, onSourceClick }: Props) {
  const extensions = useMemo(
    () => [
      Document.extend({ content: "sentence+" }),
      Text,
      UndoRedo,
      Dropcursor,
      SentenceNode.configure({ onSourceClick }),
    ],
    [onSourceClick],
  );

  const editor = useEditor(
    {
      extensions,
      content: sectionToDoc(section, report),
      editable,
      immediatelyRender: false,
      onUpdate: ({ editor: e }) => onChange(docToSection(section, e.getJSON() as TipTapDoc)),
    },
    [extensions],
  );

  useEffect(() => {
    editor?.setEditable(editable);
  }, [editor, editable]);

  // nouveau rapport (après sauvegarde ou génération) : on repeint les statuts
  useEffect(() => {
    if (!editor) return;
    editor.commands.setContent(sectionToDoc(section, report), { emitUpdate: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, report, section.section_key]);

  const tpv = report?.tpv;
  return (
    <div className="section-editor">
      {tpv !== undefined && (
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
          <span className="tpv" data-testid={`tpv-${section.section_key}`}>
            <span className="tpv-bar" aria-hidden style={{ background: "var(--line)" }}>
              <i style={{ width: `${Math.round(tpv * 100)}%`, background: "var(--ok)" }} />
            </span>
            {m.tpv} : {Math.round(tpv * 100)} %
          </span>
          <span className="legend">
            <span><i style={{ background: "var(--ok)" }} />{m.legend.verified}</span>
            <span><i style={{ background: "#f2a900" }} />{m.legend.warning}</span>
            <span><i style={{ background: "var(--bad)" }} />{m.legend.failed}</span>
          </span>
        </div>
      )}
      {section.status === "insufficient_evidence" && (
        <p className="badge warn plain" role="note" style={{ borderRadius: 4 }}>
          {m.insufficient}
          {section.missing_evidence ? ` — ${section.missing_evidence}` : ""}
        </p>
      )}
      <EditorContent editor={editor} />
    </div>
  );
}
