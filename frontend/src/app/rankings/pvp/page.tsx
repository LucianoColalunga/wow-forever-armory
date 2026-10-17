import type { Metadata } from "next";

import { FilterBar } from "@/components/FilterBar";
import { RankingMethodNote } from "@/components/RankingMethodNote";
import { Badge, Card, DataBanners, EmptyState, ErrorState, PageHeader, Pagination, StatCard } from "@/components/ui";
import { RankingTable } from "@/components/views/RankingTable";
import { SpecSummaryTable } from "@/components/views/SpecSummaryTable";
import { ApiError, apiGet } from "@/lib/api";
import { first, getDataset, pageParam } from "@/lib/dataset";
import { fmtDate, fmtInt } from "@/lib/format";
import { classOptions, metricOptions, specOptions } from "@/lib/options";
import type { Instance, PvpMode, RankingResponse, SpecSummary } from "@/lib/types";

export const metadata: Metadata = {
  title: "Ranking PvP · Darkspear Islands",
  description:
    "Ranking PvP de World of Warcraft: Forever en campos de batalla confirmados: daño a jugadores, DPS, curación, golpes de gracia y rendimiento por especialización.",
  alternates: { canonical: "/rankings/pvp" },
};

const METRICS = ["damage_to_players", "dps", "hps", "healing_effective", "killing_blows", "deaths"];

interface PvpRanking extends RankingResponse {
  battleground: Instance | null;
  battlegrounds: Instance[];
  modes: PvpMode[];
  summary: SpecSummary;
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
  const faction = ["alliance", "horde"].includes(first(sp.faction) ?? "") ? (first(sp.faction) as string) : "";
  const rawQ = (first(sp.q) ?? "").trim().slice(0, 24);
  const q = rawQ.length >= 2 ? rawQ : "";
  const page = pageParam(sp);
  let data: PvpRanking;
  let allBgs: Instance[] = [];
  try {
    [data, allBgs] = await Promise.all([
      apiGet<PvpRanking>("/rankings/pvp", {
        dataset,
        metric,
        method,
        battleground: bg,
        class: cls,
        spec,
        faction,
        q,
        page,
        page_size: 50,
      }),
      apiGet<Instance[]>("/battlegrounds"),
    ]);
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref="/rankings/pvp" />;
  }
  const params = { metric, method, battleground: bg, class: cls, spec, faction, q };
  const specHref = (c: string, sp: string | null) => {
    const next = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...params, class: c, spec: sp ?? "", q: "" })) if (v) next.set(k, v);
    return `/rankings/pvp?${next.toString()}`;
  };
  const summary = data.summary;
  const bgName = data.battleground?.name ?? "Campos de batalla";
  return (
    <>
      <PageHeader
        eyebrow="Rankings PvP"
        title={bgName}
        subtitle="Rendimiento en campos de batalla confirmados para Forever, calculado desde combat logs importados. No existe PvP puntuado: este sitio no publica ratings."
      />
      <DataBanners meta={data.data} />
      <FilterBar
        resetKeys={["spec"]}
        filters={[
          { name: "q", label: "Buscar personaje", type: "search", value: q, placeholder: "Nombre…" },
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
          {
            name: "faction",
            label: "Facción",
            type: "select",
            value: faction,
            options: [
              { value: "", label: "Ambas" },
              { value: "alliance", label: "Alianza" },
              { value: "horde", label: "Horda" },
            ],
          },
          { name: "class", label: "Clase", type: "select", value: cls, options: classOptions() },
          { name: "spec", label: "Spec", type: "select", value: spec, options: specOptions(cls || undefined) },
        ]}
      />
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Partidas registradas" value={fmtInt(summary.matches)} />
        <StatCard label="Jugadores" value={fmtInt(summary.players)} hint={faction ? (faction === "horde" ? "Horda" : "Alianza") : undefined} />
        <StatCard label="Specs con datos" value={fmtInt(summary.specs.length)} />
        <StatCard label="Última partida" value={summary.last_at ? fmtDate(summary.last_at) : "—"} />
      </div>
      <RankingMethodNote meta={data.meta} extra={data.meta.partial_data_note} />
      {data.total === 0 ? (
        q ? (
          <EmptyState title={`Ningún personaje coincide con «${q}»`}>
            Probá con otra parte del nombre o quitá filtros de clase y facción.
          </EmptyState>
        ) : (
          <EmptyState title="Todavía no hay partidas registradas">
            Importá un combat log grabado en un campo de batalla confirmado para ver datos acá.
          </EmptyState>
        )
      ) : (
        <>
          {q && (
            <p className="mb-2 text-xs text-muted" role="status">
              {data.total} resultado{data.total === 1 ? "" : "s"} para «{q}». La columna # muestra la posición real en el ranking.
            </p>
          )}
          <RankingTable rows={data.rows} metric={metric} metricLabel={data.meta.metric_label} method={method} kind="pvp" />
        </>
      )}
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} basePath="/rankings/pvp" params={params} />
      <div className="mt-6 grid gap-4 lg:grid-cols-[3fr_2fr]">
        <Card title={`Rendimiento por especialización · ${data.meta.metric_label}`}>
          <p className="mb-3 text-xs text-muted">
            Mediana del mejor valor de cada jugador{faction ? ` (${faction === "horde" ? "Horda" : "Alianza"})` : ""} en este campo
            de batalla y período. Cada jugador cuenta una vez. Tocá una spec para ver su ranking.
          </p>
          <SpecSummaryTable summary={summary} metric={metric} metricLabel={data.meta.metric_label} hrefFor={specHref} />
        </Card>
        <Card title="Modalidades PvP en Forever">
          <ul className="space-y-2 text-sm">
            {data.modes.map((m) => (
              <li key={m.key}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-ink">{m.label}</span>
                  <Badge status={m.status} />
                </div>
                <p className="mt-0.5 text-xs text-muted">{m.detail}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <Card title="Campos de batalla y verificación" className="mt-4">
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
