/**
 * Proxy de mismo origen hacia la API FastAPI.
 *
 * Permite cookies HttpOnly SameSite y CSRF sin CORS. La URL de la API se lee en tiempo de
 * ejecución (API_INTERNAL_URL), así la misma imagen sirve para cualquier entorno.
 */

import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const FORWARD_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "content-length",
  "cookie",
  "x-csrf-token",
  "authorization",
  "x-api-key",
  "x-request-id",
  "user-agent",
];
const FORWARD_RESPONSE_HEADERS = [
  "content-type",
  "cache-control",
  "retry-after",
  "x-request-id",
  "content-disposition",
  "content-security-policy",
  "x-content-type-options",
  "x-frame-options",
  "referrer-policy",
];

function apiBase(): string {
  return (process.env.API_INTERNAL_URL || "http://localhost:8000").replace(/\/$/, "");
}

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  if (path.some((p) => p === ".." || p.includes("\\"))) {
    return Response.json({ detail: "Ruta inválida." }, { status: 400 });
  }
  const target = `${apiBase()}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  for (const h of FORWARD_REQUEST_HEADERS) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  // Se usa el ÚLTIMO valor de X-Forwarded-For: lo agrega el salto inmediato (Next.js o el proxy
  // de confianza). El primero lo controla el cliente y podría falsificarse para evadir el rate limit.
  const fwd = req.headers.get("x-forwarded-for");
  const clientIp = fwd?.split(",").pop()?.trim() || req.headers.get("x-real-ip");
  if (clientIp) headers.set("x-forwarded-for", clientIp);
  // En Vercel el proxy no tiene IP fija: la API sólo acepta esta IP si viene con el secreto compartido.
  const secret = process.env.PROXY_SHARED_SECRET;
  if (secret && clientIp) {
    headers.set("x-wfa-proxy-secret", secret);
    headers.set("x-wfa-client-ip", clientIp);
  }

  const init: RequestInit & { duplex?: "half" } = { method: req.method, headers, redirect: "manual" };
  if (!["GET", "HEAD"].includes(req.method)) {
    init.body = req.body;
    init.duplex = "half";
  }
  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch {
    return Response.json({ detail: "La API no responde." }, { status: 502 });
  }
  const out = new Headers();
  for (const h of FORWARD_RESPONSE_HEADERS) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  for (const c of upstream.headers.getSetCookie()) out.append("set-cookie", c);
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { proxy as DELETE, proxy as GET, proxy as PATCH, proxy as POST };
