import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProfileCard from "@/components/ProfileCard";
import RecommendationsView from "@/components/RecommendationsView";
import { api } from "@/lib/api";
import type { ProjectProfile, RecommendationsOverview } from "@/lib/api-types";

const router = { push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const profil: ProjectProfile = {
  dossier_id: "d",
  name: "Mission",
  client_name: "Commission",
  client_request: "",
  request_summary: "",
  start_date: "2026-09-01",
  end_date: null,
  logo: null,
  documents: 2,
  audit_reports: 1,
  updated_at: null,
};

const vue = (status: "ecart" | "ok" | "non_detectees"): RecommendationsOverview => ({
  alerts: status === "ok" ? 0 : 1,
  validated: 0,
  active: 2,
  reports: [
    {
      document_id: "doc1",
      filename: "rapport.pdf",
      pages: 53,
      check: { status, expected: status === "non_detectees" ? null : 3, extracted: 2, missing: status === "ecart" ? [3] : [], duplicates: [] },
      recommendations:
        status === "non_detectees"
          ? []
          : [
              { id: "r1", document_id: "doc1", number: 1, page: 42, title: "Compléter le cadre", status: "proposed", origin: "rules", merged_into: null },
              { id: "r2", document_id: "doc1", number: 2, page: 43, title: "Surveiller les risques", status: "validated", origin: "rules", merged_into: null },
            ],
    },
  ],
});

describe("fiche projet", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("affiche la fiche puis enregistre la demande du client", async () => {
    vi.spyOn(api, "getProfile").mockResolvedValue(profil);
    const save = vi.spyOn(api, "saveProfile").mockResolvedValue({ ...profil, client_request: "Mettre en œuvre" });
    render(<ProfileCard dossierId="d" />);
    expect(await screen.findByText("Commission")).toBeInTheDocument();
    expect(screen.getByText("Demande du client non renseignée")).toBeInTheDocument();
    expect(screen.getByText("01/09/2026 – –")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("profile-edit"));
    const form = within(screen.getByTestId("profile-form"));
    fireEvent.change(form.getByLabelText("Demande du client"), { target: { value: "Mettre en œuvre" } });
    fireEvent.click(form.getByRole("button", { name: /Enregistrer/ }));
    await waitFor(() =>
      expect(save).toHaveBeenCalledWith("d", expect.objectContaining({ client_request: "Mettre en œuvre", start_date: "2026-09-01", end_date: null })),
    );
    expect(await screen.findByText("Mettre en œuvre")).toBeInTheDocument();
  });
});

describe("recommandations des rapports", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("signale l'écart et valide une recommandation", async () => {
    vi.spyOn(api, "getDossier").mockResolvedValue({ id: "d", name: "Mission", client_name: "C", language: "fr" } as never);
    const list = vi.spyOn(api, "listRecommendations").mockResolvedValue(vue("ecart"));
    const patch = vi.spyOn(api, "patchRecommendation").mockResolvedValue(vue("ok").reports[0].recommendations[0]);
    render(<RecommendationsView dossierId="d" />);
    expect(await screen.findByText("Compléter le cadre")).toBeInTheDocument();
    expect(screen.getByTestId("check-status")).toHaveTextContent("Écart");
    expect(screen.getByTestId("check-detail")).toHaveTextContent("Manquant : n° 3");
    expect(screen.getByTestId("recos-alerts")).toBeInTheDocument();
    fireEvent.click(within(screen.getByTestId("reco-r1")).getByRole("button", { name: /Valider/ }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("r1", { status: "validated" }));
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  });

  it("ne laisse jamais un rapport sans titre numéroté à zéro silencieux", async () => {
    vi.spyOn(api, "getDossier").mockResolvedValue({ id: "d", name: "Mission", client_name: "C", language: "fr" } as never);
    vi.spyOn(api, "listRecommendations").mockResolvedValue(vue("non_detectees"));
    const none = vi.spyOn(api, "setNoRecommendation").mockResolvedValue(vue("ok"));
    render(<RecommendationsView dossierId="d" />);
    expect(await screen.findByText(/Recommandations non détectées/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ce rapport ne contient aucune recommandation" }));
    await waitFor(() => expect(none).toHaveBeenCalledWith("d", "doc1", true));
  });
});
