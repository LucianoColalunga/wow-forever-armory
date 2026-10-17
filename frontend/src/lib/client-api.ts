"use client";

/** Acceso a la API desde el navegador (mismo origen, vía el proxy /api de Next.js). */

export class ClientApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

export function csrfToken(): string | null {
  return readCookie("wfa_csrf");
}

async function parse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* sin cuerpo JSON */
  }
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body && typeof (body as { detail: unknown }).detail === "string"
        ? (body as { detail: string }).detail
        : `Error ${res.status}`;
    throw new ClientApiError(res.status, detail);
  }
  return body as T;
}

export async function clientGet<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== "") qs.set(k, String(v));
  const url = `/api/v1${path}${qs.toString() ? `?${qs}` : ""}`;
  return parse<T>(await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } }));
}

export async function clientSend<T>(method: "POST" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const csrf = csrfToken();
  if (csrf) headers["X-CSRF-Token"] = csrf;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return parse<T>(res);
}

interface UploadStarted {
  upload_id: string;
  chunk_size: number;
  max_bytes: number;
}

function writeHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json", ...extra };
  const csrf = csrfToken();
  if (csrf) headers["X-CSRF-Token"] = csrf;
  return headers;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Sube un archivo por partes (la web en Vercel acepta como máximo 4,5 MB por pedido).
 * Cada parte se reintenta ante cortes de red o errores 5xx; un 4xx corta la subida.
 * Devuelve el estado y el cuerpo de la respuesta final de la API.
 */
export async function uploadInChunks(
  file: Blob & { name: string },
  fields: Record<string, string>,
  onProgress: (pct: number) => void,
  { retries = 3, backoffMs = 800 }: { retries?: number; backoffMs?: number } = {},
): Promise<{ status: number; body: unknown }> {
  const started = await clientSend<UploadStarted>("POST", "/reports/uploads", { file_name: file.name, size: file.size });
  const base = `/api/v1/reports/uploads/${encodeURIComponent(started.upload_id)}`;
  const parts = Math.max(1, Math.ceil(file.size / started.chunk_size));
  try {
    for (let i = 0; i < parts; i++) {
      const chunk = file.slice(i * started.chunk_size, Math.min(file.size, (i + 1) * started.chunk_size));
      for (let attempt = 0; ; attempt++) {
        let res: Response | null = null;
        try {
          res = await fetch(`${base}/chunks/${i}`, {
            method: "POST",
            credentials: "same-origin",
            headers: writeHeaders({ "Content-Type": "application/octet-stream" }),
            body: chunk,
          });
        } catch {
          res = null;
        }
        if (res?.ok) break;
        if (res && res.status < 500 && res.status !== 429) await parse(res);
        if (attempt >= retries) {
          if (res) await parse(res);
          throw new ClientApiError(0, "Se cortó la conexión durante la subida. Probá de nuevo.");
        }
        await sleep(backoffMs * (attempt + 1));
      }
      onProgress(Math.round(((i + 1) / parts) * 100));
    }
    const form = new URLSearchParams(fields);
    const res = await fetch(`${base}/complete`, {
      method: "POST",
      credentials: "same-origin",
      headers: writeHeaders({ "Content-Type": "application/x-www-form-urlencoded" }),
      body: form,
    });
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    return { status: res.status, body };
  } catch (err) {
    // Libera el espacio en el servidor; si falla, la sesión vence sola.
    fetch(base, { method: "DELETE", credentials: "same-origin", headers: writeHeaders() }).catch(() => undefined);
    throw err;
  }
}
