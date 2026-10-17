import type { Metadata } from "next";

import { FilterBar } from "@/components/FilterBar";
import { RankingMethodNote } from "@/components/RankingMethodNote";
import { DataBanners, EmptyState, ErrorState, PageHeader, Pagination } from "@/components/ui";
import { RankingTable } from "@/components/views/RankingTable";
import { ApiError, apiGet } from "@/lib/api";
import { first, getDataset, pageParam } from "@/lib/dataset";
import { METHOD_OPTIONS, classOptions, metricOptions, roleOptions, seasonOptions, specOptions } from "@/lib/options";
import type { Instance, RankingResponse, Season } from "@/lib/types";

export const metadata: Metadata = {
  title: "Ranking general PvE",
  description: "Ranking PvE de World of Warcraft: Forever por bandas y jefes: DPS, HPS, absorciones, supervivencia y percentiles por clase.",
  alternates: { canonical: "/rankings/pve" },
};

const GENERAL = ["dps", "hps", "aps", "damage_done", "healing_effective", "absorbs_provided", "interrupts", "dispels", "survival_pct"];
const DEFAULT_ROLE: Record<string, string> = { dps: "dps", damage_done: "dps", hps: "healer", healing_effective: "healer" };

type SP = Record<string, string | string[] | undefined>;

export default async function RankingPvePage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const dataset = await getDataset(sp);
  const metric = GENERAL.includes(first(sp.metric) ?? "") ? (first(sp.metric) as string) : "dps";
  const method = ["peak", "consistency", "percentile"].includes(first(sp.method) ?? "") ? (first(sp.method) as string) : "peak";
  const role = first(sp.role) ?? DEFAULT_ROLE[metric] ?? "";
  const cls = first(sp.class) ?? "";
  const spec = first(sp.spec) ?? "";
  const instance = first(sp.instance) ?? "";
  const season = first(sp.season_id) ?? "";
  const from = first(sp.date_from) ?? "";
  const page = pageParam(sp);

  let data: RankingResponse;
  let raids: Instance[] = [];
  let dungeons: Instance[] = [];
  let seasons: Season[] = [];
  try {
    [data, raids, dungeons, seasons] = await Promise.all([
      apiGet<RankingResponse>("/rankings/pve", {
        dataset, metric, method, role: role === "all" ? "" : role, class: cls, spec, instance,
        season_id: season, date_from: from ? `${from}T00:00:00Z` : "", page, page_size: 50,
      }),
      apiGet<Instance[]>("/raids"),
      apiGet<Instance[]>("/dungeons"),
      apiGet<Season[]>("/meta/seasons"),
    ]);
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref="/rankings/pve" />;
  }

  return (
    <>
      <PageHeader
        eyebrow="Rankings PvE"
        title="Ranking general"
        subtitle="Combina varios jefes sin comparar DPS bruto entre encuentros distintos: cada registro se normaliza dentro de su propio encuentro, dificultad y tamaño de grupo."
      />
      <DataBanners meta={data.data} />
      <FilterBar
        resetKeys={["spec"]}
        filters={[
          { name: "metric", label: "Métrica", type: "select", value: metric, options: metricOptions(GENERAL) },
          { name: "method", label: "Método", type: "select", value: method, options: METHOD_OPTIONS },
          {
            name: "instance",
            label: "Banda o mazmorra",
            type: "select",
            value: instance,
            options: [
              { value: "", label: "Todas" },
              ...raids.map((r) => ({ value: r.slug, label: `Banda · ${r.name}` })),
              ...dungeons.map((d) => ({ value: d.slug, label: `Mazmorra · ${d.name}` })),
            ],
          },
          { name: "role", label: "Rol", type: "select", value: role, options: [{ value: "all", label: "Todos" }, ...roleOptions().slice(1)] },
          { name: "class", label: "Clase", type: "select", value: cls, options: classOptions() },
          { name: "spec", label: "Spec", type: "select", value: spec, options: specOptions(cls || undefined) },
          { name: "season_id", label: "Temporada / fase", type: "select", value: season, options: seasonOptions(seasons) },
          { name: "date_from", label: "Desde", type: "date", value: from },
        ]}
      />
      <RankingMethodNote meta={data.meta} />
      {data.total === 0 ? (
        <EmptyState title="Sin resultados para estos filtros">
          Puede que no haya kills rankeables o que ninguna cubeta alcance la muestra mínima del método elegido. Probá
          con el método «A · Pico» o quitá filtros.
        </EmptyState>
      ) : (
        <RankingTable rows={data.rows} metric={metric} metricLabel={data.meta.metric_label} method={method} kind="general" />
      )}
      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        basePath="/rankings/pve"
        params={{ metric, method, role, class: cls, spec, instance, season_id: season, date_from: from }}
      />
    </>
  );
}
