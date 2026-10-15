import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { InstancePage, type InstancePayload } from "@/components/InstancePage";
import { ErrorState } from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";
import { getDataset } from "@/lib/dataset";

export const metadata: Metadata = { title: "Banda" };

export default async function RaidPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const dataset = await getDataset(await searchParams);
  if (!/^[a-z0-9-]{1,64}$/.test(id)) notFound();
  try {
    const data = await apiGet<InstancePayload>(`/raids/${id}`, { dataset });
    return <InstancePage data={data} />;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref={`/raids/${id}`} />;
  }
}
