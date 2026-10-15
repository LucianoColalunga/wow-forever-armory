import { afterEach, describe, expect, it, vi } from "vitest";

import { ClientApiError, clientGet, clientSend } from "./client-api";

afterEach(() => {
  vi.restoreAllMocks();
  document.cookie = "wfa_csrf=; max-age=0; path=/";
});

describe("client-api", () => {
  it("envía el token CSRF de la cookie en escrituras", async () => {
    document.cookie = "wfa_csrf=token-123; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await clientSend("POST", "/admin/rankings/rebuild", { reason: "prueba" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/admin/rankings/rebuild");
    expect((init?.headers as Record<string, string>)["X-CSRF-Token"]).toBe("token-123");
    expect(init?.credentials).toBe("same-origin");
  });

  it("propaga el detalle de error de la API", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Acceso restringido" }), { status: 403 }));
    await expect(clientGet("/admin/overview")).rejects.toMatchObject({ status: 403, message: "Acceso restringido" });
    await expect(clientGet("/admin/overview")).rejects.toBeInstanceOf(ClientApiError);
  });

  it("arma la query string sin parámetros vacíos", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
    await clientGet("/search", { q: "brak", dataset: "demo", limit: undefined });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/search?q=brak&dataset=demo");
  });
});
