import Link from "next/link";

import { DashboardCharts } from "@/components/views/DashboardCharts";
import { Badge, Card, ClassName, DataBanners, EmptyState, ErrorState, PageHeader, StatCard } from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";
import { getDataset } from "@/lib/dataset";
import { fmtDate, fmtDateTime, fmtDec, fmtDuration, fmtInt, partitionLabel } from "@/lib/format";
import type { DataMeta, Encounter, Instance, SourceInfo } from "@/lib/types";

interface Overview {
  counts: Record<string, number>;
  latest_kills: {
    fight_id: number;
    encounter: Encounter | null;
    instance: Instance | null;
    difficulty_id: number | null;
    group_size: number | null;
    start_at: string;
    duration_ms: number;
    report_public_id: string;
  }[];
  highlights: {
    metric: string;
    value: number;
    character_id: number;
    name: string;
    class_slug: string | null;
    spec: string | null;
    fight_id: number;
    encounter: Encounter | null;
    difficulty_id: number | null;
    group_size: number | null;
  }[];
  activity: { day: string; fights: number }[];
  meta: DataMeta;
}

const HIGHLIGHT_LABEL: Record<string, string> = { dps: "Mayor DPS", hps: "Mayor HPS efectivo", aps: "Más absorciones/s" };

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const dataset = await getDataset(sp);
  let data: Overview;
  let sources: SourceInfo[] = [];
  try {
    [data, sources] = await Promise.all([
      apiGet<Overview>("/stats/overview", { dataset }),
      apiGet<SourceInfo[]>("/meta/sources"),
    ]);
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref="/" />;
  }
  const c = data.counts;
  return (
    <>
      <PageHeader
        eyebrow="World of Warcraft: Forever"
        title="Panorama competitivo"
        subtitle="Rankings y estadísticas construidos a partir de combat logs importados. Ningún dato es oficial de Blizzard; cada número indica cuántos registros y qué método lo respaldan."
      />
      <DataBanners meta={data.meta} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Reportes" value={fmtInt(c.reports)} />
        <StatCard label="Combates" value={fmtInt(c.fights)} hint="Sin duplicados" />
        <StatCard label="Kills" value={fmtInt(c.kills)} />
        <StatCard label="Personajes" value={fmtInt(c.characters)} />
        <StatCard label="Hermandades" value={fmtInt(c.guilds)} />
        <StatCard label="Jefes" value={fmtInt(c.bosses)} />
      </div>

      {c.reports === 0 ? (
        <div className="mt-6">
          <EmptyState title={dataset === "real" ? "Todavía no hay datos reales" : "No hay datos de demostración"}>
            {dataset === "real" ? (
              <>
                WoW: Forever se lanza el 4/11/2026 y no tiene API oficial: los datos llegan importando combat logs.{" "}
                <Link href="/import" className="text-gold-strong underline">
                  Importá el primero
                </Link>{" "}
                o pasá al modo <strong>Demo</strong> (arriba a la derecha) para explorar con datos sintéticos.
              </>
            ) : (
              <>Un administrador puede generarlos con <code>python -m app.cli seed-demo</code>.</>
            )}
          </EmptyState>
        </div>
      ) : (
        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <Card title="Destacados de la última semana con datos" className="lg:col-span-1">
            <ul className="space-y-3">
              {data.highlights.length === 0 && <li className="text-sm text-muted">Sin kills rankeables recientes.</li>}
              {data.highlights.map((h) => (
                <li key={h.metric} className="rounded-lg border border-line p-3">
                  <p className="text-xs uppercase tracking-wider text-faint">{HIGHLIGHT_LABEL[h.metric] ?? h.metric}</p>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <ClassName name={h.name} classSlug={h.class_slug} spec={h.spec} href={`/players/${h.character_id}`} />
                    <span className="num font-display text-lg text-gold-strong">{fmtDec(h.value)}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    <Link href={`/encounters/${h.fight_id}`} className="hover:underline">
                      {h.encounter?.name ?? "Encuentro"} · {partitionLabel(h.difficulty_id, h.group_size)}
                    </Link>
                  </p>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="Últimos kills" className="lg:col-span-2">
            <ul className="divide-y divide-line/70">
              {data.latest_kills.map((k) => (
                <li key={k.fight_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <div>
                    <Link href={`/encounters/${k.fight_id}`} className="font-medium text-ink hover:text-gold-strong">
                      {k.encounter?.name ?? "Encuentro"}
                    </Link>
                    <span className="ml-2 text-xs text-muted">
                      {k.instance?.name ?? "Instancia sin asociar"} · {partitionLabel(k.difficulty_id, k.group_size)}
                    </span>
                  </div>
                  <span className="num text-xs text-muted">
                    {fmtDuration(k.duration_ms)} · {fmtDateTime(k.start_at)}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="Actividad" className="lg:col-span-2">
            <DashboardCharts activity={data.activity.map((a) => ({ label: fmtDate(a.day), value: a.fights }))} />
          </Card>
          <Card title="Fuentes de datos" className="lg:col-span-1" actions={<Link href="/sources" className="text-xs text-gold-strong underline">Detalle</Link>}>
            <ul className="space-y-2 text-sm">
              {sources.map((s) => (
                <li key={s.key} className="flex items-center justify-between gap-2">
                  <span className="text-muted">{s.label}</span>
                  <Badge status={s.status} />
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
      <p className="mt-6 text-xs text-faint">Última actualización: {fmtDateTime(data.meta.last_processed_at)}</p>
    </>
  );
}
