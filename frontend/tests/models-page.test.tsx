import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ModelsPage from "@/app/admin/models/page";
import { api } from "@/lib/api";
import type { ModelCard, ModelsOverview } from "@/lib/api-types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({}),
  usePathname: () => "/admin/models",
}));

const card = (name: string, over: Partial<ModelCard> = {}): ModelCard => ({
  name, digest: "sha256:abcdef0123456789abcdef", size_bytes: 1_400_000_000, family: "qwen3", parameter_size: "1.7B",
  quantization: "Q4_K_M", max_context: null, capabilities: ["completion"], license: "Apache License", active: false,
  role: "generation", test: null, ...over,
});

const overview: ModelsOverview = {
  engine: { reachable: true, provider: "ollama" },
  active: "a:1", configured: "a:1", embedding_model: null, previous: null,
  models: [card("a:1", { active: true }), card("b:2")],
  history: [],
  limits: {
    model: { max_context: null, vision: null, capabilities: null },
    engine: { allocated_context: 4096, allocated_source: "default", loaded_context: null, vram_bytes: null, gpu_layers: null, keep_alive: "30m" },
    app: { response_reserved: 700, max_upload_mb: 25, formats: ["PDF"], images_used: false, saturation: ["Constats : lots.", "Sections : non envoyés."] },
  },
  context: { unit: "tokens", estimated: true, window_allocated: 4096, window_max: null, system: 224, context: 200, passages: 2900, response_reserved: 700, free: 72, passages_unsent: 600, passages_unsent_count: 2 },
};

describe("page Modèles", () => {
  beforeEach(() => {
    vi.spyOn(api, "listModels").mockResolvedValue(overview);
    vi.spyOn(api, "contextBudget").mockResolvedValue(overview.context);
  });

  it("annonce un exemple simulé, formate les nombres et n'écrit pas « Inconnu jetons »", async () => {
    const { container } = render(<ModelsPage />);
    await waitFor(() => expect(screen.getAllByText(/Exemple simulé/).length).toBeGreaterThan(0));
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/Inconnu jetons/);
    expect(text).toMatch(/1,4\s?Go/);
    expect(text).toContain("Constats : lots.");
  });

  it("garde « Activer » désactivé tant que le test n'est pas réussi", async () => {
    render(<ModelsPage />);
    const buttons = await screen.findAllByRole("button", { name: "Activer" });
    expect(buttons).toHaveLength(1);
    expect((buttons[0] as HTMLButtonElement).disabled).toBe(true);
  });
});
