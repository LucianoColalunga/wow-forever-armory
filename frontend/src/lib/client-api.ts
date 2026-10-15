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

/** Subida con progreso (XMLHttpRequest permite medir bytes enviados). */
export function uploadWithProgress(
  form: FormData,
  onProgress: (pct: number) => void,
): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/reports/import");
    xhr.withCredentials = true;
    const csrf = csrfToken();
    if (csrf) xhr.setRequestHeader("X-CSRF-Token", csrf);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = null;
      }
      resolve({ status: xhr.status, body });
    };
    xhr.onerror = () => reject(new ClientApiError(0, "No se pudo conectar con el servidor."));
    xhr.send(form);
  });
}
