import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FindingsView from "@/components/FindingsView";
import SourcePanel from "@/components/SourcePanel";
import { api } from "@/lib/api";
import type { ChunkDetail, Finding } from "@/lib/api-types";

// routeur STABLE : un nouvel objet à chaque rendu relançait le chargement et écrasait l'état (test instable)
const { push, router } = vi.hoisted(() => {
  const push = vi.fn();
  return { push, router: { push } };
});
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const finding: Finding = {
  id: "f1",
  dossier_id: "d",
  text: "Clôture trop longue",
  theme: "Finance",
  severity: "high",
  source_ids: ["c1"],
  validated: false,
};

const chunk: ChunkDetail = {
  id: "c1",
  dossier_id: "d",
  document_id: "doc",
  document: "diag.pdf",
  text: "<img src=x onerror=alert(1)> Le délai est de 12 jours.",
  page_start: 3,
  page_end: 3,
  section_path: ["Finance", "Clôture"],
  injection_flags: ["IGNORE_INSTRUCTIONS"],
};

describe("page constats", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    push.mockReset();
  });

  it("valide un constat via PATCH et met à jour l'affichage", async () => {
    vi.spyOn(api, "listFindings").mockResolvedValue([finding]);
    const patch = vi
      .spyOn(api, "patchFinding")
      .mockResolvedValue({ ...finding, validated: true });
    render(<FindingsView dossierId="d" />);
    const box = await screen.findByRole("checkbox");
    fireEvent.click(box);
    await waitFor(() => expect(patch).toHaveBeenCalledWith("f1", { validated: true }));
    expect(await screen.findByText("Validé", {}, { timeout: 3000 })).toBeInTheDocument();  // CI plus lente
  });

  it("corrige le texte d'un constat", async () => {
    vi.spyOn(api, "listFindings").mockResolvedValue([finding]);
    const patch = vi
      .spyOn(api, "patchFinding")
      .mockResolvedValue({ ...finding, text: "Clôture à 8 jours" });
    render(<FindingsView dossierId="d" />);
    fireEvent.click(await screen.findByText("Corriger"));
    fireEvent.change(screen.getByLabelText("Corriger"), { target: { value: "Clôture à 8 jours" } });
    fireEvent.click(screen.getByText("Enregistrer"));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("f1", { text: "Clôture à 8 jours" }));
    expect(await screen.findByText(/Clôture à 8 jours/)).toBeInTheDocument();
  });

  it("une source cliquable ouvre le panneau latéral", async () => {
    vi.spyOn(api, "listFindings").mockResolvedValue([finding]);
    vi.spyOn(api, "getChunk").mockResolvedValue(chunk);
    render(<FindingsView dossierId="d" />);
    fireEvent.click(await screen.findByText(/^Preuve 1/));
    expect(await screen.findByText("diag.pdf")).toBeInTheDocument();
  });
});

describe("panneau source", () => {
  it("affiche le texte brut (pas de HTML interprété) et l'alerte d'injection", async () => {
    vi.spyOn(api, "getChunk").mockResolvedValue(chunk);
    const { container } = render(<SourcePanel chunkId="c1" onClose={() => {}} />);
    expect(await screen.findByText(/onerror=alert/)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/Contenu suspect détecté/)).toBeInTheDocument();
    expect(screen.getByText(/page 3/)).toBeInTheDocument();
    expect(screen.getByText(/Finance › Clôture/)).toBeInTheDocument();
  });

  it("404 : message d'erreur", async () => {
    const { ApiError } = await import("@/lib/api");
    vi.spyOn(api, "getChunk").mockRejectedValue(new ApiError(404, "NOT_FOUND", "Passage introuvable"));
    render(<SourcePanel chunkId="zz" onClose={() => {}} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Passage introuvable");
  });
});
