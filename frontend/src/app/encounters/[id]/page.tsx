import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge, DataBanners, ErrorState, PageHeader, Pill } from "@/components/ui";
import { FightView } from "@/components/views/FightView";
import { ApiError, apiGet } from "@/lib/api";
import { getDataset } from "@/lib/dataset";
import { fmtDateTime, fmtDuration, fmtPct, partitionLabel } from "@/lib/format";
import type { DataMeta, FightDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Combate" };

const REASONS: Record<string, string> = {
  duplicado: "Duplicado de otro reporte: no suma a rankings ni estadísticas.",
  incompleto: "Combate incompleto (archivo cortado o /reload): no es rankeable.",
  duracion_minima: "Duró menos que el mínimo rankeable.",
  revision_outlier: "Valores fuera de lo esperable: pendiente de revisión de un admin.",
  excluido_por_admin: "Excluido por un admin (ver auditoría).",
  no_rankeable: "Los recorridos de mazmorra se muestran como historial, no se rankean.",
};

export default async function EncounterPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const dataset = await getDataset(await searchParams);
  let fight: FightDetail;
  try {
    fight = await apiGet<FightDetail>(`/encounters/${id}`, { dataset });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref={`/encounters/${id}`} />;
  }
  const meta: DataMeta = {
    dataset: fight.dataset,
    is_demo: fight.dataset === "demo",
    data_version: 0,
    last_processed_at: null,
    stale: false,
    generated_at: "",
  };
  const title = fight.encounter?.name ?? fight.zone_name ?? "Combate";
  return (
    <>
      <PageHeader
        eyebrow={
          <>
            {fight.instance ? (
              <Link
                href={`/${fight.instance.kind === "raid" ? "raids" : fight.instance.kind === "dungeon" ? "dungeons" : "rankings/pvp"}${
                  fight.instance.kind === "battleground" ? "" : `/${fight.instance.slug}`
                }`}
                className="hover:underline"
              >
                {fight.instance.name}
              </Link>
            ) : (
              fight.zone_name ?? "Instancia sin asociar"
            )}
            {fight.kind === "encounter" && ` · ${partitionLabel(fight.difficulty_id, fight.group_size)}`}
          </>
        }
        title={title}
        subtitle={`${fmtDateTime(fight.start_at)} · duración ${fmtDuration(fight.duration_ms)} · ${fight.participants.length} jugadores`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {fight.kind === "encounter" &&
              (fight.success ? (
                <Pill tone="good">Kill</Pill>
              ) : (
                <Pill tone="bad">Wipe{fight.boss_min_hp_pct !== null ? ` · jefe al ${fmtPct(fight.boss_min_hp_pct, 1)}` : ""}</Pill>
              ))}
            {fight.instance && <Badge status={fight.instance.verification} />}
            {fight.encounter && (
              <Link href={`/rankings/pve/bosses/${fight.encounter.id}`} className="text-sm text-gold-strong hover:underline">
                Ranking del jefe →
              </Link>
            )}
          </div>
        }
      />
      <DataBanners meta={meta} />
      {(!fight.rankable || fight.duplicate_of_id) && (
        <p className="mb-4 rounded-lg border border-warning/50 bg-warning/10 px-4 py-2 text-sm text-warning" role="note">
          {REASONS[fight.unrankable_reason ?? ""] ?? "Este combate no cuenta para rankings."}
          {fight.duplicate_of_id && (
            <>
              {" "}
              <Link href={`/encounters/${fight.duplicate_of_id}`} className="underline">
                Ver el combate original
              </Link>
            </>
          )}
        </p>
      )}
      <FightView fight={fight} />
    </>
  );
}
