import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AckBar, ExportBar, TransitionBar } from "./ActionBars";
import { deliverables } from "./client";
import { docToSection, sectionToDoc } from "./convert";
import RoadmapView from "./RoadmapView";
import SectionEditor from "./SectionEditor";
import type { Deliverable, SectionDraft, SectionReport } from "./types";

const section: SectionDraft = {
  section_key: "contexte",
  status: "ok",
  missing_evidence: null,
  sentences: [
    { text: "Le délai est de 12 jours.", kind: "fact", source_labels: ["P1"], source_ids: ["c1"], finding_ids: ["f1"] },
    { text: "Il faut réduire ce délai.", kind: "recommendation", source_labels: [], source_ids: [], finding_ids: [] },
    { text: "<b>Chiffre inventé : 99 %</b>", kind: "fact", source_labels: ["P2"], source_ids: ["c2", "c3"], finding_ids: [] },
  ],
};

const report: SectionReport = {
  tpv: 1 / 3,
  report: {
    section_key: "contexte",
    issues: [],
    checks: [
      { index: 0, status: "verified", numbers_cited: 1, numbers_found: 1, support: 0.9 },
      { index: 1, status: "warning", numbers_cited: 0, numbers_found: 0, support: 0.2 },
      { index: 2, status: "failed", numbers_cited: 1, numbers_found: 0, support: 0.1 },
    ],
  },
};

describe("conversion contenu API <-> document TipTap", () => {
  it("aller-retour sans perte", () => {
    const back = docToSection(section, sectionToDoc(section, report));
    expect(back).toEqual(section);
  });

  it("le statut est porté par le nœud, pas par le contenu", () => {
    const doc = sectionToDoc(section, report);
    expect(doc.content.map((n) => n.attrs?.status)).toEqual(["verified", "warning", "failed"]);
    expect(sectionToDoc(section).content.map((n) => n.attrs?.status)).toEqual([null, null, null]);
  });

  it("section vide : un nœud jetable, supprimé au retour", () => {
    const empty: SectionDraft = { ...section, status: "insufficient_evidence", sentences: [], missing_evidence: "rien" };
    expect(docToSection(empty, sectionToDoc(empty))).toEqual(empty);
  });
});

describe("SectionEditor", () => {
  it("colore les phrases selon leur statut et affiche le TPV", async () => {
    const { container } = render(
      <SectionEditor section={section} report={report} editable onChange={() => {}} onSourceClick={() => {}} />,
    );
    await waitFor(() => expect(container.querySelectorAll("[data-sentence]").length).toBe(3));
    const statuses = [...container.querySelectorAll("[data-sentence]")].map((e) => e.getAttribute("data-status"));
    expect(statuses).toEqual(["verified", "warning", "failed"]);
    expect(screen.getByTestId("tpv-contexte")).toHaveTextContent("33 %");
  });

  it("le clic sur [n] transmet l'identifiant du passage ; le HTML du texte n'est pas interprété", async () => {
    const onSource = vi.fn();
    const { container } = render(
      <SectionEditor section={section} report={report} editable={false} onChange={() => {}} onSourceClick={onSource} />,
    );
    await waitFor(() => expect(container.querySelectorAll("[data-source]").length).toBe(3));
    fireEvent.click(container.querySelectorAll("[data-source]")[2]);
    expect(onSource).toHaveBeenCalledWith("c3");
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toContain("<b>Chiffre inventé");
  });

  it("refus de preuves : bandeau explicite", async () => {
    render(
      <SectionEditor
        section={{ ...section, status: "insufficient_evidence", sentences: [], missing_evidence: "aucun budget" }}
        editable
        onChange={() => {}}
        onSourceClick={() => {}}
      />,
    );
    expect(await screen.findByRole("note")).toHaveTextContent("aucun budget");
    await act(async () => {});
  });
});

describe("transitions et exports", () => {
  it("export désactivé hors approved, actif quand approved", () => {
    const { rerender } = render(<ExportBar state="in_review" onExport={() => {}} />);
    for (const b of screen.getAllByRole("button")) expect(b).toBeDisabled();
    const onExport = vi.fn();
    rerender(<ExportBar state="approved" onExport={onExport} />);
    const pdf = screen.getByRole("button", { name: "PDF" });
    expect(pdf).toBeEnabled();
    fireEvent.click(pdf);
    expect(onExport).toHaveBeenCalledWith("pdf");
  });

  it("le refus exige un motif", () => {
    const onT = vi.fn();
    render(<TransitionBar state="in_review" role="reviewer" onTransition={onT} />);
    fireEvent.click(screen.getByText("Refuser"));
    fireEvent.click(screen.getByText("Confirmer"));
    expect(screen.getByRole("alert")).toHaveTextContent(/motif/i);
    expect(onT).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(/Motif/), { target: { value: "chiffres faux" } });
    fireEvent.click(screen.getByText("Confirmer"));
    expect(onT).toHaveBeenCalledWith("rejected", "chiffres faux");
  });

  it("l'acquittement exige un motif et le transmet", () => {
    const onAck = vi.fn();
    render(<AckBar items={[{ index: 2, label: "Acquitter #3" }, { index: -1, label: "Acquitter le refus" }]} onAck={onAck} />);
    const button = screen.getByText("Acquitter #3");
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Motif de l'acquittement/), { target: { value: "vérifié sur pièce" } });
    fireEvent.click(button);
    expect(onAck).toHaveBeenCalledWith(2, "vérifié sur pièce");
  });

  it("un consultant ne voit pas approuver/refuser ; brouillon : soumettre seulement", () => {
    const { rerender } = render(<TransitionBar state="in_review" role="consultant" onTransition={() => {}} />);
    expect(screen.queryByText("Approuver")).toBeNull();
    expect(screen.getByText("Retirer")).toBeInTheDocument();
    rerender(<TransitionBar state="draft" role="consultant" onTransition={() => {}} />);
    expect(screen.getByText("Soumettre à relecture")).toBeInTheDocument();
  });
});

describe("feuille de route", () => {
  const deliverable = {
    id: "r1",
    dossier_id: "d",
    type: "roadmap",
    state: "draft",
    template_id: "t",
    version: 1,
    reports: [],
    content: {
      type: "roadmap",
      language: "fr",
      template_id: "t",
      template_version: "1",
      sections: [],
      roadmap: {
        criteria: [{ key: "impact", label: "Impact", weight: 1, higher_is_better: true }],
        items: [
          { rank: 1, wave: 1, score: 0.75, initiative: { id: "I1", title: "Automatiser", description: "", finding_ids: [], scores: [{ key: "impact", value: 4, source_ids: [], rationale: "r" }], depends_on: ["I2"], duration_weeks: 6 } },
          { rank: 2, wave: 2, score: 0.5, initiative: { id: "I2", title: "Former", description: "", finding_ids: [], scores: [{ key: "impact", value: 3, source_ids: [], rationale: "r" }], depends_on: ["I1"], duration_weeks: null } },
        ],
        topo_order: [],
        cycles: [["I1", "I2", "I1"]],
        critical_path: [],
      },
    },
  } as unknown as Deliverable;

  beforeEach(() => vi.restoreAllMocks());

  it("alerte de cycle et PATCH des scores modifiés", async () => {
    vi.spyOn(deliverables, "get").mockResolvedValue(deliverable);
    const patch = vi.spyOn(deliverables, "patchRoadmap").mockResolvedValue({});
    render(<RoadmapView id="r1" />);
    expect(await screen.findByTestId("cycle-alert")).toHaveTextContent("I1 → I2 → I1");
    fireEvent.change(screen.getByLabelText("Automatiser Impact"), { target: { value: "5" } });
    fireEvent.click(screen.getByText("Recalculer"));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith("r1", [{ id: "I1", scores: [{ key: "impact", value: 5 }] }]),
    );
  });
});
