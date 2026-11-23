import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContextView from "@/components/ContextView";
import { api } from "@/lib/api";
import type { ChatReply, ContextSheet } from "@/lib/api-types";

const router = { push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const empty = { sector: "", size: "", country: "", language: "", project_types: [], scope: "", constraints: "", stakeholders: "" };
const sheet: ContextSheet = { dossier_id: "d", data: empty, confirmed: false, confirmed_at: null, missing: [], flags: [] };
const reply: ChatReply = {
  status: "ok",
  reply: "Quel budget ?",
  questions: ["Quel budget ?"],
  proposals: {
    fields: [{ field: "sector", value: "Administration", current: "" }],
    decisions: [{ category: "budget", label: "budget", text: "Budget de 40 000 euros" }],
  },
  dropped: [],
  sent: { passages: 1, history_turns: 0, history_dropped: 0 },
};

describe("fiche de contexte et chat", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("le chat propose : rien n'est enregistré avant le clic de l'utilisateur", async () => {
    vi.spyOn(api, "getContext").mockResolvedValue(sheet);
    const chat = vi.spyOn(api, "chat").mockResolvedValue(reply);
    const create = vi.spyOn(api, "createDecision").mockResolvedValue({ id: "dec_9" } as never);
    const confirm = vi.spyOn(api, "confirmDecision").mockResolvedValue({} as never);
    const saveCtx = vi.spyOn(api, "saveContext").mockResolvedValue({ ...sheet, confirmed: true });
    render(<ContextView dossierId="d" />);
    const box = within(await screen.findByTestId("chat"));
    fireEvent.change(box.getByLabelText("Votre message"), { target: { value: "Budget de 40 000 euros" } });
    fireEvent.click(box.getByRole("button", { name: /Envoyer/ }));
    await waitFor(() => expect(chat).toHaveBeenCalledWith("d", "Budget de 40 000 euros", []));
    expect(await screen.findByTestId("proposal-decision")).toHaveTextContent("Budget de 40 000 euros");
    expect(create).not.toHaveBeenCalled();
    expect(saveCtx).not.toHaveBeenCalled();
    // accepter un champ le reporte dans le formulaire, sans l'enregistrer
    fireEvent.click(within(screen.getByTestId("proposal-field-sector")).getByRole("button"));
    expect((within(screen.getByTestId("context-form")).getByLabelText("Secteur") as HTMLInputElement).value).toBe("Administration");
    expect(saveCtx).not.toHaveBeenCalled();
    // confirmer une décision crée une décision confirmée
    fireEvent.click(within(screen.getByTestId("proposal-decision")).getByRole("button", { name: /Confirmer la décision/ }));
    await waitFor(() => expect(create).toHaveBeenCalledWith("d", { category: "budget", text: "Budget de 40 000 euros" }));
    await waitFor(() => expect(confirm).toHaveBeenCalledWith("dec_9"));
  });

  it("confirme la fiche", async () => {
    vi.spyOn(api, "getContext").mockResolvedValue(sheet);
    const saveCtx = vi.spyOn(api, "saveContext").mockResolvedValue({ ...sheet, confirmed: true, confirmed_at: "2026-11-23T10:00:00Z", confirmed_by_name: "Claire" });
    render(<ContextView dossierId="d" />);
    fireEvent.click(await screen.findByRole("button", { name: /Confirmer la fiche/ }));
    await waitFor(() => expect(saveCtx).toHaveBeenCalledWith("d", { ...empty, confirm: true }));
    expect(await screen.findByText("Fiche confirmée par Claire, 2026-11-23")).toBeInTheDocument();
  });

  it("refus explicite quand la fenêtre est pleine", async () => {
    vi.spyOn(api, "getContext").mockResolvedValue(sheet);
    vi.spyOn(api, "chat").mockResolvedValue({ ...reply, status: "refused", reason: "fenêtre de contexte pleine", reply: "", questions: [], proposals: { fields: [], decisions: [] } });
    render(<ContextView dossierId="d" />);
    const box = within(await screen.findByTestId("chat"));
    fireEvent.change(box.getByLabelText("Votre message"), { target: { value: "Bonjour" } });
    fireEvent.click(box.getByRole("button", { name: /Envoyer/ }));
    expect(await screen.findByText(/Fenêtre de contexte pleine/)).toBeInTheDocument();
  });
});
