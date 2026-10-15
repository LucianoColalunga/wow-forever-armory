import type { Metadata } from "next";

import { FilterBar } from "@/components/FilterBar";
import { DataBanners, EmptyState, ErrorState, PageHeader, Pagination } from "@/components/ui";
import { FightList } from "@/components/views/FightList";
import { ApiError, apiGet } from "@/lib/api";
import { first, getDataset, pageParam } from "@/lib/dataset";
import type { FightSummary, Instance, Paged } from "@/lib/types";

export const metadata: Metadata = { title: "Historial de combates" };

type SP = Record<string, string | string[] | undefined>;

export default async function EncountersPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const dataset = await getDataset(sp);
  const kind = first(sp.kind) ?? "";
  const instance = first(sp.instance) ?? "";
  const success = first(sp.success) ?? "";
  const bossId = first(sp.boss_id) ?? "";
  const from = first(sp.date_from) ?? "";
  const to = first(sp.date_to) ?? "";
  const dups = first(sp.include_duplicates) ?? "";
  const sort = first(sp.sort) ?? "recent";
  const page = pageParam(sp);
  let data: Paged<FightSummary>;
  let raids: Instance[] = [];
  let dungeons: Instance[] = [];
  let bgs: Instance[] = [];
  try {
    [data, raids, dungeons, bgs] = await Promise.all([
      apiGet<Paged<FightSummary>>("/encounters", {
        dataset, kind, instance, success, boss_id: bossId, sort, include_duplicates: dups,
        date_from: from ? `${from}T00:00:00Z` : "", date_to: to ? `${to}T23:59:59Z` : "", page, page_size: 50,
      }),
      apiGet<Instance[]>("/raids"),
      apiGet<Instance[]>("/dungeons"),
      apiGet<Instance[]>("/battlegrounds"),
    ]);
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref="/encounters" />;
  }
  return (
    <>
      <PageHeader
        eyebrow="Historial"
        title="Combates registrados"
        subtitle="Kills, wipes, recorridos de mazmorra y partidas de campo de batalla. Los duplicados (el mismo combate subido por otra persona) se ocultan por defecto."
      />
      <DataBanners meta={data.meta} />
      <FilterBar
        filters={[
          {
            name: "kind",
            label: "Tipo",
            type: "select",
            value: kind,
            options: [
              { value: "", label: "Todos" },
              { value: "encounter", label: "Jefes" },
              { value: "dungeon_run", label: "Recorridos de mazmorra" },
              { value: "battleground", label: "Campos de batalla" },
            ],
          },
          {
            name: "instance",
            label: "Instancia",
            type: "select",
            value: instance,
            options: [{ value: "", label: "Todas" }, ...[...raids, ...dungeons, ...bgs].map((i) => ({ value: i.slug, label: i.name }))],
          },
          {
            name: "success",
            label: "Resultado",
            type: "select",
            value: success,
            options: [
              { value: "", label: "Todos" },
              { value: "true", label: "Kills" },
              { value: "false", label: "Wipes" },
            ],
          },
          {
            name: "sort",
            label: "Orden",
            type: "select",
            value: sort,
            options: [
              { value: "recent", label: "Más recientes" },
              { value: "oldest", label: "Más antiguos" },
              { value: "duration", label: "Más rápidos" },
            ],
          },
          { name: "date_from", label: "Desde", type: "date", value: from },
          { name: "date_to", label: "Hasta", type: "date", value: to },
          {
            name: "include_duplicates",
            label: "Duplicados",
            type: "select",
            value: dups,
            options: [
              { value: "", label: "Ocultar" },
              { value: "true", label: "Mostrar" },
            ],
          },
        ]}
      />
      {data.total === 0 ? (
        <EmptyState title="No hay combates con estos filtros" />
      ) : (
        <FightList fights={data.items} showReport />
      )}
      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        basePath="/encounters"
        params={{ kind, instance, success, boss_id: bossId, sort, include_duplicates: dups, date_from: from, date_to: to }}
      />
    </>
  );
}
