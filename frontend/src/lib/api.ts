import "server-only";

/** Acceso a la API desde el servidor de Next.js (Server Components). */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function apiBase(): string {
  return (process.env.API_INTERNAL_URL || "http://localhost:8000").replace(/\/$/, "");
}

type Params = Record<string, string | number | boolean | null | undefined>;

export function withParams(path: string, params?: Params): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== null && v !== undefined && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `${path}?${s}` : path;
}

export async function apiGet<T>(path: string, params?: Params): Promise<T> {
  const url = `${apiBase()}/api/v1${withParams(path, params)}`;
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store", headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError(503, "La API no responde. Verificá que el backend esté en marcha.");
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

/** Variante que devuelve null ante 404 (para páginas de detalle). */
export async function apiGetOrNull<T>(path: string, params?: Params): Promise<T | null> {
  try {
    return await apiGet<T>(path, params);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}
