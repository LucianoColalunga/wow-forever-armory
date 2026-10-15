import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { FilterBar } from "@/components/FilterBar";
import { RankingMethodNote } from "@/components/RankingMethodNote";
import { Badge, DataBanners, EmptyState, ErrorState, PageHeader, Pagination } from "@/components/ui";
import { DistributionChart } from "@/components/views/DistributionChart";
import { RankingTable } from "@/components/views/RankingTable";
import { ApiError, apiGet } from "@/lib/api";
import { first, getDataset, pageParam } from "@/lib/dataset";
import { DIFFICULTY_NOTE, partitionLabel } from "@/lib/format";
import { METHOD_OPTIONS, classOptions, metricOptions, roleOptions, specOptions } from "@/lib/options";
import type { Encounter, Instance, RankingResponse } from "@/lib/types";

export const metadata: Metadata = { title: "Ranking por jefe" };

const DEFAULT_ROLE: Record<string, string> = { dps: "dps", damage_done: "dps", hps: "healer", healing_effective: "healer" };

const METRICS = ["dps", "hps", "aps", "damage_done", "healing_effective", "absorbs_provided", "damage_taken", "dtps", "deaths", "survival_pct", "interrupts", "dispels"];

interface BossRanking extends RankingResponse {
  encounter: Encounter;
  instance: Instance | null;
  partitions: { difficulty_id: number | null; group_size: number | null; entries: number; kills: number }[];
  distribution: { bins: { from: number; to: number; count: number }[]; count: number };
}

type SP = Record<string, string | string[] | undefined>;

export default async function BossRankingPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<SP> }) {
  const { id } = await params;
  const sp = await searchParams;
  if (!/^\d+$/.test(id)) notFound();
  const dataset = await getDataset(sp);
  const metric = METRICS.includes(first(sp.metric) ?? "") ? (first(sp.metric) as string) : "dps";
  const method = ["peak", "consistency", "percentile"].includes(first(sp.method) ?? "") ? (first(sp.method) as string) : "peak";
  const cls = first(sp.class) ?? "";
  const spec = first(sp.spec) ?? "";
  const role = first(sp.role) ?? DEFAULT_ROLE[metric] ?? "";
  const part = first(sp.partition) ?? "";
  const [difficulty, size] = part ? part.split("-") : ["", ""];
  const page = pageParam(sp);

  let data: BossRanking;
  try {
    data = await apiGet<BossRanking>(`/rankings/pve/bosses/${id}`, {
      dataset, metric, method, class: cls, spec, role: role === "all" ? "" : role, difficulty_id: difficulty, group_size: size, page, page_size: 50,
    });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref={`/rankings/pve/bosses/${id}`} />;
  }
  const currentPart = `${data.meta.difficulty_id ?? ""}-${data.meta.group_size ?? ""}`;

  return (
    <>
      <PageHeader
        eyebrow={
          <>
            {data.instance ? (
              <Link href={`/${data.instance.kind === "raid" ? "raids" : "dungeons"}/${data.instance.slug}`} className="hover:underline">
                {data.instance.name}
              </Link>
            ) : (
              "Instancia sin asociar"
            )}{" "}
            · Ranking por jefe
          </>
        }
        title={data.encounter.name}
        subtitle={`Sólo se comparan kills del mismo jefe, dificultad y tamaño de grupo. ${DIFFICULTY_NOTE}`}
        actions={data.instance ? <Badge status={data.instance.verification} /> : null}
      />
      <DataBanners meta={data.data} />
      <FilterBar
        resetKeys={["spec"]}
        filters={[
          {
            name: "partition",
            label: "Dificultad y tamaño",
            type: "select",
            value: currentPart,
            options: data.partitions.map((p) => ({
              value: `${p.difficulty_id ?? ""}-${p.group_size ?? ""}`,
              label: `${partitionLabel(p.difficulty_id, p.group_size)} (${p.kills} kills)`,
            })),
          },
          { name: "metric", label: "Métrica", type: "select", value: metric, options: metricOptions(METRICS) },
          { name: "method", label: "Método", type: "select", value: method, options: METHOD_OPTIONS },
          { name: "role", label: "Rol", type: "select", value: role, options: [{ value: "all", label: "Todos" }, ...roleOptions().slice(1)] },
          { name: "class", label: "Clase", type: "select", value: cls, options: classOptions() },
          { name: "spec", label: "Spec", type: "select", value: spec, options: specOptions(cls || undefined) },
        ]}
      />
      <RankingMethodNote meta={data.meta} />
      {data.distribution.count > 0 && (
        <div className="card mb-4 p-4">
          <DistributionChart bins={data.distribution.bins} metric={metric} label={data.meta.metric_label} />
        </div>
      )}
      {data.total === 0 ? (
        <EmptyState title="Sin resultados para estos filtros">
          Ninguna entrada cumple la muestra mínima del método o los filtros elegidos.
        </EmptyState>
      ) : (
        <RankingTable rows={data.rows} metric={metric} metricLabel={data.meta.metric_label} method={method} kind="partition" />
      )}
      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        basePath={`/rankings/pve/bosses/${id}`}
        params={{ metric, method, class: cls, spec, role, partition: part }}
      />
    </>
  );
}
