import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, getToken, setToken } from "@/lib/api";

function reply(status: number, body?: unknown) {
  return Promise.resolve(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

describe("client API", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    setToken(null);
    fetchMock.mockReset();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("login stocke le jeton et l'envoie ensuite en Bearer", async () => {
    fetchMock.mockReturnValueOnce(reply(200, { token: "tok", user: { id: "u", role: "admin" } }));
    await api.login("a@b.c", "x");
    expect(getToken()).toBe("tok");
    expect(sessionStorage.getItem("cadrage.token")).toBe("tok");

    fetchMock.mockReturnValueOnce(reply(200, []));
    await api.listDossiers();
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toContain("/api/v1/dossiers");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok");
  });

  it("401 : erreur typée et jeton effacé", async () => {
    setToken("vieux");
    fetchMock.mockReturnValueOnce(
      reply(401, { error: { code: "UNAUTHORIZED", message: "Authentification requise" } }),
    );
    const err = await api.listDossiers().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 401, code: "UNAUTHORIZED" });
    expect(getToken()).toBeNull();
  });

  it("404 et 409 : code et message du serveur", async () => {
    fetchMock.mockReturnValueOnce(reply(404, { error: { code: "NOT_FOUND", message: "Dossier introuvable" } }));
    await expect(api.getDossier("x")).rejects.toMatchObject({ status: 404, code: "NOT_FOUND" });
    fetchMock.mockReturnValueOnce(
      reply(409, { error: { code: "DUPLICATE_DOCUMENT", message: "déjà importé" } }),
    );
    await expect(api.uploadDocument("d", new File(["x"], "a.txt"))).rejects.toMatchObject({
      status: 409,
      code: "DUPLICATE_DOCUMENT",
    });
  });

  it("l'import envoie un multipart sans Content-Type forcé", async () => {
    fetchMock.mockReturnValueOnce(reply(201, { document_id: "d", chunks: 2, alerts: 0 }));
    await api.uploadDocument("dos", new File(["x"], "a.txt"));
    const init = fetchMock.mock.calls[0][1];
    expect(init.body).toBeInstanceOf(FormData);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("erreur non JSON : message par défaut", async () => {
    fetchMock.mockReturnValueOnce(Promise.resolve(new Response("oops", { status: 500 })));
    await expect(api.listDossiers()).rejects.toMatchObject({ status: 500, code: "HTTP_500" });
  });
});
