import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { deliverables } from "@/components/editor/client";
import DeliverableView from "@/components/editor/DeliverableView";
import type { Deliverable } from "@/components/editor/types";

const router = vi.hoisted(() => ({ push: vi.fn() }));  // routeur stable entre les rendus
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const d: Deliverable = {
  id: "dl1",
  dossier_id: "d",
  type: "tor",
  state: "draft",
  template_id: "tor-fr-standard",
  version: 1,
  modules: ["training"],
  content: { type: "tor", language: "fr", template_id: "tor-fr-standard", template_version: "1.0", sections: [], roadmap: null, modules: ["training"] },
  reports: [],
  sections: [
    { key: "contexte", title: "Contexte", requires_decisions: [], requires_labels: [] },
    { key: "profil", title: "Profil", requires_decisions: ["profile"], requires_labels: ["profil"] },
    { key: "frm_formateurs", title: "Profil des formateurs", requires_decisions: ["profile"], requires_labels: ["profil"] },
  ],
};

describe("gabarit par type de projet", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("affiche les sections des modules et les décisions exigées", async () => {
    vi.spyOn(deliverables, "get").mockResolvedValue(d);
    vi.spyOn(deliverables, "versions").mockResolvedValue([]);
    vi.spyOn(deliverables, "comments").mockResolvedValue([]);
    vi.spyOn(deliverables, "me").mockResolvedValue({ id: "u", role: "consultant" });
    render(<DeliverableView id="dl1" />);
    expect(await screen.findByTestId("section-frm_formateurs")).toBeInTheDocument();
    expect(screen.getByText("Profil des formateurs")).toBeInTheDocument(); // titre venu du gabarit
    expect(screen.getAllByText("Décision requise : profil")).toHaveLength(2);
    expect(screen.getByTestId("modules")).toHaveTextContent("Formation");
    expect(screen.queryByTestId("section-contexte")?.textContent).not.toMatch(/Décision requise/);
  });
});
