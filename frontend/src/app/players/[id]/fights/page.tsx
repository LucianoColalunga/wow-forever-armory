import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DataBanners, EmptyState, ErrorState, PageHeader, Pagination } from "@/components/ui";
import { RecentFights } from "@/components/views/PlayerProfileView";
import { ApiError, apiGet } from "@/lib/api";
import { first, getDataset, pageParam } from "@/lib/dataset";
import type { Character, FightSummary, Paged, Participant } from "@/lib/types";

export const metadata: Metadata = { title: "Historial del personaje" };

export default async function PlayerFightsPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const sp = await searchParams;
  const dataset = await getDataset(sp);
  const page = pageParam(sp);
  const kind = first(sp.kind) ?? "";
  let data: Paged<FightSummary & { performance: Participant }>;
  let character: Character;
  try {
    const [d, prof] = await Promise.all([
      apiGet<Paged<FightSummary & { performance: Participant }>>(`/players/${id}/fights`, { dataset, page, page_size: 50, kind }),
      apiGet<{ character: Character }>(`/players/${id}`, { dataset }),
    ]);
    data = d;
    character = prof.character;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} />;
  }
  return (
    <>
      <PageHeader
        eyebrow={<Link href={`/players/${id}`} className="hover:underline">← {character.name}</Link>}
        title="Historial de combates"
        subtitle="Todos los combates visibles del personaje (sin duplicados)."
      />
      <DataBanners meta={data.meta} />
      {data.total === 0 ? <EmptyState title="Sin combates" /> : <RecentFights fights={data.items} />}
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} basePath={`/players/${id}/fights`} params={{ kind }} />
    </>
  );
}
