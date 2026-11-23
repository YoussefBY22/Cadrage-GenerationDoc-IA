import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { docToSection, sectionToDoc } from "@/components/editor/convert";
import type { SectionDraft } from "@/components/editor/types";
import DecisionsView from "@/components/DecisionsView";
import { api } from "@/lib/api";
import type { Decision } from "@/lib/api-types";

const router = { push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const dec: Decision = {
  id: "dec_1",
  dossier_id: "d",
  category: "profile",
  text: "Un chef de projet senior",
  status: "proposed",
  author_id: "usr_dev",
  author_name: "Claire",
  created_at: "2026-11-23T10:00:00Z",
};

describe("décisions humaines", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("enregistre puis confirme une décision", async () => {
    const list = vi.spyOn(api, "listDecisions").mockResolvedValue([dec]);
    const create = vi.spyOn(api, "createDecision").mockResolvedValue(dec);
    const confirm = vi.spyOn(api, "confirmDecision").mockResolvedValue({ ...dec, status: "confirmed" });
    render(<DecisionsView dossierId="d" />);
    expect(await screen.findByText("Un chef de projet senior")).toBeInTheDocument();
    const form = within(screen.getByTestId("decision-form"));
    fireEvent.change(form.getByLabelText("Décision"), { target: { value: "Budget de 40 000 euros" } });
    fireEvent.change(form.getByLabelText("Catégorie"), { target: { value: "budget" } });
    fireEvent.click(form.getByRole("button", { name: /Enregistrer et confirmer/ }));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith("d", { category: "budget", text: "Budget de 40 000 euros" }),
    );
    await waitFor(() => expect(confirm).toHaveBeenCalledWith("dec_1")); // second appel, distinct
    fireEvent.click(await screen.findByRole("button", { name: /^Confirmer/ }));
    await waitFor(() => expect(confirm).toHaveBeenCalledWith("dec_1"));
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1));
  });

  it("montre « Décision de <auteur>, <date> » pour une décision confirmée", async () => {
    vi.spyOn(api, "listDecisions").mockResolvedValue([
      { ...dec, status: "confirmed", confirmed_at: "2026-11-23T12:00:00Z" },
    ]);
    render(<DecisionsView dossierId="d" />);
    expect(await screen.findByText("Décision de Claire, 2026-11-23")).toBeInTheDocument();
  });
});

describe("éditeur : les décisions citées survivent à l'édition", () => {
  it("conserve decision_ids à l'aller-retour", () => {
    const section: SectionDraft = {
      section_key: "profil",
      status: "ok",
      missing_evidence: null,
      sentences: [{ text: "Chef de projet senior.", kind: "fact", source_labels: [], source_ids: [], finding_ids: [], decision_ids: ["dec_1"] }],
    };
    const back = docToSection(section, sectionToDoc(section));
    expect(back.sentences[0].decision_ids).toEqual(["dec_1"]);
  });
});
