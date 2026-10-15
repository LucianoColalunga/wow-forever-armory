import type { Metadata } from "next";

import { FilterBar } from "@/components/FilterBar";
import { DataBanners, EmptyState, ErrorState, PageHeader, Pagination } from "@/components/ui";
import { PlayerList } from "@/components/views/PlayerList";
import { ApiError, apiGet } from "@/lib/api";
import { first, getDataset, pageParam } from "@/lib/dataset";
import { classOptions, specOptions } from "@/lib/options";
import type { Character, Paged } from "@/lib/types";

export const metadata: Metadata = { title: "Personajes" };

type SP = Record<string, string | string[] | undefined>;

export default async function PlayersPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const dataset = await getDataset(sp);
  const q = (first(sp.q) ?? "").slice(0, 64);
  const cls = first(sp.class) ?? "";
  const spec = first(sp.spec) ?? "";
  const sort = first(sp.sort) ?? "last_seen";
  const page = pageParam(sp);
  let data: Paged<Character>;
  try {
    data = await apiGet<Paged<Character>>("/players", { dataset, q, class: cls, spec, sort, page, page_size: 50 });
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref="/players" />;
  }
  return (
    <>
      <PageHeader eyebrow="Armería" title="Personajes" subtitle="Personajes vistos en los combat logs importados." />
      <DataBanners meta={data.meta} />
      <form action="/players" method="get" className="mb-3 flex gap-2" role="search">
        <label htmlFor="players-q" className="sr-only">
          Buscar personaje
        </label>
        <input
          id="players-q"
          name="q"
          defaultValue={q}
          maxLength={64}
          placeholder="Nombre del personaje"
          className="w-full max-w-sm rounded-lg border border-line bg-surface px-3 py-1.5 text-sm"
        />
        <button className="rounded-lg border border-gold px-3 py-1.5 text-sm text-gold-strong hover:bg-gold/10">Buscar</button>
      </form>
      <FilterBar
        resetKeys={["spec"]}
        filters={[
          { name: "class", label: "Clase", type: "select", value: cls, options: classOptions() },
          { name: "spec", label: "Spec", type: "select", value: spec, options: specOptions(cls || undefined) },
          {
            name: "sort",
            label: "Orden",
            type: "select",
            value: sort,
            options: [
              { value: "last_seen", label: "Actividad reciente" },
              { value: "fights", label: "Más combates" },
              { value: "name", label: "Nombre" },
            ],
          },
        ]}
      />
      {data.total === 0 ? <EmptyState title="No encontramos personajes con esos criterios" /> : <PlayerList players={data.items} />}
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} basePath="/players" params={{ q, class: cls, spec, sort }} />
    </>
  );
}
