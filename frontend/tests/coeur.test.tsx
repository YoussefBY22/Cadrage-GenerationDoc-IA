import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { deliverables } from "@/components/editor/client";
import RoadmapView from "@/components/editor/RoadmapView";
import type { Coherence, Deliverable } from "@/components/editor/types";
import PrioritiesView from "@/components/PrioritiesView";
import ProjectsView from "@/components/ProjectsView";
import { api } from "@/lib/api";
import type { ExistingProject, Priority } from "@/lib/api-types";

const router = { push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const prio: Priority = {
  id: "prt_1",
  dossier_id: "d",
  title: "Fiabiliser la paie",
  description: "Priorité DG",
  rank: 1,
  status: "proposed",
  source_ids: [],
  author_id: "usr_dev",
  created_at: "2026-11-22T10:00:00Z",
};

describe("priorités institutionnelles", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("ajoute une priorité et change son statut", async () => {
    const list = vi.spyOn(api, "listPriorities").mockResolvedValue([prio]);
    const create = vi.spyOn(api, "createPriority").mockResolvedValue(prio);
    vi.spyOn(api, "me").mockResolvedValue({ id: "u", role: "reviewer" });
    const validate = vi.spyOn(api, "validatePriority").mockResolvedValue({ ...prio, status: "validated" });
    render(<PrioritiesView dossierId="d" />);
    expect(await screen.findByText("Fiabiliser la paie")).toBeInTheDocument();
    const form = within(screen.getByTestId("priority-form"));
    fireEvent.change(form.getByLabelText("Titre"), { target: { value: "Réduire les coûts" } });
    fireEvent.click(form.getByRole("button", { name: /Ajouter/ }));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith("d", { title: "Réduire les coûts", description: "" }),
    );
    fireEvent.click(await screen.findByRole("button", { name: /Valider/ }));
    await waitFor(() => expect(validate).toHaveBeenCalledWith("prt_1"));
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1)); // rechargé après chaque action
  });
});

describe("priorités : validation réservée", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("un consultant ne voit pas de bouton de validation et lit un nom, pas un identifiant", async () => {
    vi.spyOn(api, "listPriorities").mockResolvedValue([{ ...prio, author_name: "Camille Laurent" }]);
    vi.spyOn(api, "me").mockResolvedValue({ id: "u", role: "consultant" });
    render(<PrioritiesView dossierId="d" />);
    expect(await screen.findByText("Camille Laurent")).toBeInTheDocument();
    expect(screen.queryByText("usr_dev")).toBeNull();
    expect(screen.queryByRole("button", { name: /Valider/ })).toBeNull();
    expect(screen.getByText("Validation par un relecteur")).toBeInTheDocument();
  });
});

describe("projets existants", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("crée un projet avec état et durée facultative", async () => {
    const proj: ExistingProject = {
      id: "prj_1",
      dossier_id: "d",
      title: "Socle SI",
      state: "in_progress",
      duration_weeks: null,
      depends_on: [],
      source_ids: [],
      author_id: "usr_dev",
      created_at: null,
    };
    vi.spyOn(api, "listProjects").mockResolvedValue([proj]);
    const create = vi.spyOn(api, "createProject").mockResolvedValue(proj);
    render(<ProjectsView dossierId="d" />);
    expect(await screen.findByText("Socle SI")).toBeInTheDocument();
    const form = within(screen.getByTestId("project-form"));
    fireEvent.change(form.getByLabelText("Titre"), { target: { value: "Portail" } });
    fireEvent.change(form.getByLabelText("État"), { target: { value: "planned" } });
    fireEvent.click(form.getByRole("button", { name: /Ajouter/ }));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith("d", { title: "Portail", state: "planned", duration_weeks: null }),
    );
  });
});

const roadmapDeliverable: Deliverable = {
  id: "r1",
  dossier_id: "d",
  type: "roadmap",
  state: "draft",
  template_id: "roadmap_fr",
  version: 1,
  reports: [],
  content: {
    type: "roadmap",
    language: "fr",
    template_id: "roadmap_fr",
    template_version: "1",
    sections: [],
    roadmap: {
      criteria: [{ key: "impact", label: "Impact", weight: 1, higher_is_better: true }],
      items: [
        {
          rank: 1,
          wave: 1,
          score: 0.8,
          initiative: {
            id: "I1",
            title: "Automatiser la paie",
            description: "",
            finding_ids: ["f1"],
            scores: [{ key: "impact", value: 4, source_ids: [], rationale: "" }],
            depends_on: [],
            duration_weeks: null,
            priority_ids: ["prt_1"],
            depends_on_projects: [],
          },
        },
      ],
      topo_order: ["I1"],
      cycles: [],
      critical_path: [],
      rejected_links: [{ initiative: "Automatiser la paie", kind: "priority", value: "PR9" }],
      passages_not_sent: 2,
    },
  },
} as unknown as Deliverable;

const coherence: Coherence = {
  issues: [
    { code: "FINDING_NO_INITIATIVE", severity: "warning", refs: { finding_id: "f2" } },
    { code: "NO_DURATION", severity: "info", refs: { initiative_id: "I1" } },
  ],
  sequence: [{ initiative_id: "I1", position: 1, start_week: null, end_week: null }],
  chains: [
    {
      initiative_id: "I1",
      title: "Automatiser la paie",
      objective: "Fiabiliser la paie",
      expected_result: "Zéro erreur",
      indicator: "Taux d'erreur",
      proposal_status: "proposed",
      proposal_flags: ["trois"],
      findings: [{ id: "f1", title: "Quatre tableurs manuels", source_ids: ["c1"], kind: "high", extra: {} }],
      priorities: [{ id: "prt_1", title: "Fiabiliser la paie", source_ids: [], kind: "1", extra: {} }],
      dependencies: [],
      source_ids: ["c1"],
      rank: 1,
      wave: 1,
      inherited_rank: null,
      position: 1,
      start_week: null,
      end_week: null,
      issues: ["NO_DURATION"],
    },
  ],
};

describe("feuille de route : cohérence", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("affiche les écarts, les liens écartés, la chaîne et ouvre la source", async () => {
    vi.spyOn(deliverables, "get").mockResolvedValue(roadmapDeliverable);
    vi.spyOn(deliverables, "coherence").mockResolvedValue(coherence);
    vi.spyOn(api, "listFindings").mockResolvedValue([
      { id: "f2", dossier_id: "d", text: "Absence de contrôle", theme: "t", severity: "high", source_ids: [], validated: true },
    ]);
    vi.spyOn(api, "listPriorities").mockResolvedValue([{ ...prio, status: "validated" }]);
    vi.spyOn(api, "listProjects").mockResolvedValue([]);
    vi.spyOn(api, "getChunk").mockResolvedValue({
      id: "c1",
      dossier_id: "d",
      document_id: "doc",
      document: "audit.pdf",
      text: "Le processus de paie repose sur quatre tableurs.",
      page_start: 4,
      page_end: 4,
      section_path: [],
      injection_flags: [],
    });
    render(<RoadmapView id="r1" />);
    const box = within(await screen.findByTestId("coherence"));
    expect(box.getByTestId("issue-FINDING_NO_INITIATIVE")).toHaveTextContent("Absence de contrôle");
    expect(box.getByTestId("issue-NO_DURATION")).toHaveTextContent("Sans durée : ordre seulement");
    expect(box.getByTestId("issue-NO_DURATION")).toHaveTextContent("1"); // regroupé par type, avec un compte
    expect(box.getByTestId("rejected-links")).toHaveTextContent("PR9");
    expect(box.getByRole("note")).toHaveTextContent("2 passage(s) non envoyé(s)");
    const chain = within(screen.getByTestId("chain-I1"));
    expect(screen.getByTestId("flags-I1")).toHaveTextContent("trois"); // proposition IA, nombre non sourcé
    expect(chain.getByText("Accepter")).toBeInTheDocument();
    expect(screen.queryByText(/ini_/)).toBeNull(); // jamais d'identifiant brut
    expect(chain.getByText("Quatre tableurs manuels")).toBeInTheDocument();
    expect(chain.getByText("Zéro erreur")).toBeInTheDocument();
    fireEvent.click(chain.getByRole("button", { name: "[1]" }));
    expect(await screen.findByText(/quatre tableurs\./)).toBeInTheDocument(); // panneau de source
    expect(screen.getByText("audit.pdf")).toBeInTheDocument();
  });

  it("masque le bloc Proposition IA quand objectif, résultat et indicateur sont vides", async () => {
    const empty = { ...coherence, chains: [{ ...coherence.chains[0], objective: "", expected_result: "", indicator: "", proposal_flags: [] }] };
    vi.spyOn(deliverables, "get").mockResolvedValue(roadmapDeliverable);
    vi.spyOn(deliverables, "coherence").mockResolvedValue(empty);
    vi.spyOn(api, "listFindings").mockResolvedValue([]);
    vi.spyOn(api, "listPriorities").mockResolvedValue([]);
    vi.spyOn(api, "listProjects").mockResolvedValue([]);
    render(<RoadmapView id="r1" />);
    const chain = within(await screen.findByTestId("chain-I1"));
    expect(screen.queryByTestId("proposal-I1")).toBeNull();
    expect(chain.queryByText("Accepter")).toBeNull();
  });
});
