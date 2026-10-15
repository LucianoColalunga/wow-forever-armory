import type { Metadata } from "next";
import Link from "next/link";

import { DataBanners, EmptyState, ErrorState, PageHeader, Pagination } from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";
import { first, getDataset, pageParam } from "@/lib/dataset";
import { fmtInt } from "@/lib/format";
import type { Paged } from "@/lib/types";

export const metadata: Metadata = { title: "Hermandades" };

interface GuildItem {
  id: number;
  name: string;
  realm: string;
  region: string;
  faction: string | null;
  members: number;
}

export default async function GuildsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const dataset = await getDataset(sp);
  const q = (first(sp.q) ?? "").slice(0, 64);
  const page = pageParam(sp);
  let data: Paged<GuildItem>;
  try {
    data = await apiGet<Paged<GuildItem>>("/guilds", { dataset, q, page, page_size: 48 });
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref="/guilds" />;
  }
  return (
    <>
      <PageHeader
        eyebrow="Armería"
        title="Hermandades"
        subtitle="Las hermandades se registran al importar un reporte. Sin API oficial, la membresía se infiere de los reportes o la corrige un admin."
      />
      <DataBanners meta={data.meta} />
      <form action="/guilds" method="get" className="mb-4 flex gap-2" role="search">
        <label htmlFor="guilds-q" className="sr-only">
          Buscar hermandad
        </label>
        <input id="guilds-q" name="q" defaultValue={q} maxLength={64} placeholder="Nombre de la hermandad" className="w-full max-w-sm rounded-lg border border-line bg-surface px-3 py-1.5 text-sm" />
        <button className="rounded-lg border border-gold px-3 py-1.5 text-sm text-gold-strong hover:bg-gold/10">Buscar</button>
      </form>
      {data.total === 0 ? (
        <EmptyState title="No hay hermandades" />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((g) => (
            <li key={g.id}>
              <Link href={`/guilds/${g.id}`} className="card block p-4 hover:border-gold">
                <p className="font-display text-lg text-ink">&lt;{g.name}&gt;</p>
                <p className="text-xs text-muted">
                  {g.realm || "Reino ?"} {g.region ? `· ${g.region.toUpperCase()}` : ""}
                  {g.faction ? ` · ${g.faction === "horde" ? "Horda" : "Alianza"}` : ""} · {fmtInt(g.members)} miembros
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} basePath="/guilds" params={{ q }} />
    </>
  );
}
