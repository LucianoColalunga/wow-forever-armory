import { afterEach, describe, expect, it, vi } from "vitest";

import { ClientApiError, clientGet, clientSend, uploadInChunks } from "./client-api";

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

  it("sube por partes, reintenta un corte de red y completa con los campos", async () => {
    document.cookie = "wfa_csrf=token-123; path=/";
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ upload_id: "abc", chunk_size: 4, max_bytes: 100 }, 201))
      .mockRejectedValueOnce(new TypeError("network"))
      .mockResolvedValueOnce(json({ received: 4, size: 10, next_index: 1 }))
      .mockResolvedValueOnce(json({ received: 8, size: 10, next_index: 2 }))
      .mockResolvedValueOnce(json({ received: 10, size: 10, next_index: 3 }))
      .mockResolvedValueOnce(json({ report_id: "R1", status: "queued" }, 202));
    const progress: number[] = [];
    const file = new File(["0123456789"], "WoWCombatLog.txt");
    const out = await uploadInChunks(file, { guild_name: "Vigilia" }, (p) => progress.push(p), { backoffMs: 0 });
    expect(out.status).toBe(202);
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls).toEqual([
      "/api/v1/reports/uploads",
      "/api/v1/reports/uploads/abc/chunks/0",
      "/api/v1/reports/uploads/abc/chunks/0",
      "/api/v1/reports/uploads/abc/chunks/1",
      "/api/v1/reports/uploads/abc/chunks/2",
      "/api/v1/reports/uploads/abc/complete",
    ]);
    expect(progress).toEqual([33, 67, 100]);
    const completeInit = fetchMock.mock.calls[5][1];
    expect(String(completeInit?.body)).toBe("guild_name=Vigilia");
    expect((completeInit?.headers as Record<string, string>)["X-CSRF-Token"]).toBe("token-123");
  });

  it("corta la subida ante un error 4xx y cancela la sesión", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ upload_id: "abc", chunk_size: 4, max_bytes: 100 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "La subida no existe o venció" }), { status: 404 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const file = new File(["0123456789"], "log.txt");
    await expect(uploadInChunks(file, {}, () => undefined, { backoffMs: 0 })).rejects.toMatchObject({ status: 404 });
    expect(fetchMock.mock.calls.at(-1)?.[1]?.method).toBe("DELETE");
  });

  it("arma la query string sin parámetros vacíos", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
    await clientGet("/search", { q: "brak", dataset: "demo", limit: undefined });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/search?q=brak&dataset=demo");
  });
});
