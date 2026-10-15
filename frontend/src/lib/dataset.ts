import "server-only";

import { cookies } from "next/headers";

import type { Dataset } from "./types";

export const DATASET_COOKIE = "wfa_dataset";

type SP = Record<string, string | string[] | undefined>;

export function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

/** Dataset activo: ?dataset= (enlace compartido) → cookie de preferencia → "real". */
export async function getDataset(searchParams?: SP): Promise<Dataset> {
  const fromQuery = first(searchParams?.dataset);
  if (fromQuery === "demo" || fromQuery === "real") return fromQuery;
  const store = await cookies();
  return store.get(DATASET_COOKIE)?.value === "demo" ? "demo" : "real";
}

export function pageParam(searchParams: SP | undefined): number {
  const n = Number(first(searchParams?.page) ?? "1");
  return Number.isInteger(n) && n > 0 && n < 10000 ? n : 1;
}
