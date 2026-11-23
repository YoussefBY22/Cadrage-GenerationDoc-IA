import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ContextGauge from "@/components/ContextGauge";
import { api, setToken } from "@/lib/api";
import type { ContextBudget } from "@/lib/api-types";

const budget: ContextBudget = {
  unit: "tokens",
  estimated: true,
  window_allocated: 4096,
  window_max: 262144,
  system: 300,
  context: 200,
  passages: 2800,
  response_reserved: 700,
  free: 96,
  passages_unsent: 700,
  passages_unsent_count: 2,
};

describe("ContextGauge", () => {
  it("montre les cinq parts de la fenêtre et les passages non envoyés", () => {
    render(<ContextGauge budget={budget} />);
    const gauge = screen.getByTestId("context-gauge");
    for (const label of ["Système", "Contexte", "Passages", "Réponse", "Libre", "Passages non envoyés"]) {
      expect(gauge.textContent).toContain(label);
    }
    expect(gauge.textContent?.replace(/\s/g, "")).toContain("2800");
    expect(gauge.textContent).toContain("2 passage(s) hors fenêtre");
    expect(gauge.querySelectorAll(".gauge-bar .seg")).toHaveLength(5);
  });

  it("indique que tout tient quand rien n'est écarté", () => {
    render(<ContextGauge budget={{ ...budget, passages_unsent: 0, passages_unsent_count: 0 }} />);
    expect(screen.getByTestId("context-gauge").textContent).toContain("Tout tient");
  });
});

describe("API modèles", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    setToken("tok");
    fetchMock.mockReset();
    fetchMock.mockImplementation(() => Promise.resolve(new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } })));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("appelle les routes d'administration avec le jeton", async () => {
    await api.listModels();
    await api.testModel("qwen3:4b");
    await api.activateModel("qwen3:4b");
    await api.rollbackModel();
    await api.contextBudget(5000);
    const calls = fetchMock.mock.calls.map(([url, init]) => [String(url).replace(/^.*\/api\/v1/, ""), init?.method ?? "GET"]);
    expect(calls).toEqual([
      ["/admin/models", "GET"],
      ["/admin/models/test", "POST"],
      ["/admin/models/activate", "POST"],
      ["/admin/models/rollback", "POST"],
      ["/admin/models/context?candidate_tokens=5000", "GET"],
    ]);
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Authorization")).toBe("Bearer tok");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ model: "qwen3:4b" });
  });
});
