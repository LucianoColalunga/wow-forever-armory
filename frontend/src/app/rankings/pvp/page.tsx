import type { Metadata } from "next";

import { FilterBar } from "@/components/FilterBar";
import { RankingMethodNote } from "@/components/RankingMethodNote";
import { Badge, Card, DataBanners, EmptyState, ErrorState, PageHeader, Pagination } from "@/components/ui";
import { RankingTable } from "@/components/views/RankingTable";
import { ApiError, apiGet } from "@/lib/api";
import { first, getDataset, pageParam } from "@/lib/dataset";
import { classOptions, metricOptions, specOptions } from "@/lib/options";
import type { Instance, PvpMode, RankingResponse } from "@/lib/types";

export const metadata: Metadata = { title: "Rankings PvP" };

const METRICS = ["damage_to_players", "dps", "hps", "healing_effective", "killing_blows", "deaths"];

interface PvpRanking extends RankingResponse {
  battleground: Instance | null;
  battlegrounds: Instance[];
  modes: PvpMode[];
}

type SP = Record<string, string | string[] | undefined>;

export default async function PvpPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const dataset = await getDataset(sp);
  const metric = METRICS.includes(first(sp.metric) ?? "") ? (first(sp.metric) as string) : "damage_to_players";
  const method = first(sp.method) === "consistency" ? "consistency" : "peak";
  const bg = first(sp.battleground) ?? "";
  const cls = first(sp.class) ?? "";
  const spec = first(sp.spec) ?? "";
  const page = pageParam(sp);
  let data: PvpRanking;
  let allBgs: Instance[] = [];
  try {
    [data, allBgs] = await Promise.all([
      apiGet<PvpRanking>("/rankings/pvp", { dataset, metric, method, battleground: bg, class: cls, spec, page, page_size: 50 }),
      apiGet<Instance[]>("/battlegrounds"),
    ]);
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref="/rankings/pvp" />;
  }
  return (
    <>
      <PageHeader
        eyebrow="Rankings PvP"
        title="Campos de batalla"
        subtitle="Sólo modalidades confirmadas para Forever. No existe rating oficial ni PvP puntuado: este sitio no publica ratings."
      />
      <DataBanners meta={data.data} />
      <div className="mb-4 grid gap-3 md:grid-cols-4">
        {data.modes.map((m) => (
          <div key={m.key} className="card p-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-ink">{m.label}</span>
              <Badge status={m.status} />
            </div>
            <p className="mt-1 text-xs text-muted">{m.detail}</p>
          </div>
        ))}
      </div>
      <FilterBar
        resetKeys={["spec"]}
        filters={[
          {
            name: "battleground",
            label: "Campo de batalla",
            type: "select",
            value: bg || data.battleground?.slug || "",
            options: data.battlegrounds.map((b) => ({ value: b.slug, label: b.name })),
          },
          { name: "metric", label: "Métrica", type: "select", value: metric, options: metricOptions(METRICS) },
          {
            name: "method",
            label: "Método",
            type: "select",
            value: method,
            options: [
              { value: "peak", label: "A · Pico (mejor partida)" },
              { value: "consistency", label: "B · Consistencia (mediana)" },
            ],
          },
          { name: "class", label: "Clase", type: "select", value: cls, options: classOptions() },
          { name: "spec", label: "Spec", type: "select", value: spec, options: specOptions(cls || undefined) },
        ]}
      />
      <RankingMethodNote meta={data.meta} extra={data.meta.partial_data_note} />
      {data.total === 0 ? (
        <EmptyState title="Todavía no hay partidas registradas">
          Importá un combat log grabado en un campo de batalla confirmado para ver datos acá.
        </EmptyState>
      ) : (
        <RankingTable rows={data.rows} metric={metric} metricLabel={data.meta.metric_label} method={method} kind="pvp" />
      )}
      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        basePath="/rankings/pvp"
        params={{ metric, method, battleground: bg, class: cls, spec }}
      />
      <Card title="Campos de batalla y verificación" className="mt-6">
        <ul className="grid gap-2 text-sm sm:grid-cols-2">
          {allBgs.map((b) => (
            <li key={b.id} className="flex items-center justify-between gap-2 rounded-md border border-line px-3 py-2">
              <span>
                {b.name} <span className="text-xs text-faint">({b.max_players} vs {b.max_players})</span>
              </span>
              <Badge status={b.verification} />
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-faint">
          Los campos «reportados por terceros» no se rankean hasta que un admin los verifique con una fuente oficial.
        </p>
      </Card>
    </>
  );
}
