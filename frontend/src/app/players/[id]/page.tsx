import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Card, DataBanners, ErrorState, PageHeader, StatCard } from "@/components/ui";
import { BestTable, type BestRow, EvolutionChart, type EvolutionPoint, RecentFights } from "@/components/views/PlayerProfileView";
import { ProfileLoadout } from "@/components/views/ProfileLoadout";
import { ApiError, apiGet } from "@/lib/api";
import { CLASS_SOURCE_LABELS, classColor, classLabel, specLabel } from "@/lib/classes";
import { getDataset } from "@/lib/dataset";
import { fmtDate, fmtDec, fmtInt } from "@/lib/format";
import type { Character, DataMeta, FightSummary, Participant } from "@/lib/types";

export const metadata: Metadata = { title: "Perfil de personaje" };

interface Profile {
  character: Character;
  summary: Record<string, number | null>;
  best_by_encounter: BestRow[];
  recent_fights: (FightSummary & { performance: Participant })[];
  evolution: EvolutionPoint[];
  meta: DataMeta;
}

export default async function PlayerPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const dataset = await getDataset(await searchParams);
  let p: Profile;
  try {
    p = await apiGet<Profile>(`/players/${id}`, { dataset });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref={`/players/${id}`} />;
  }
  const c = p.character;
  const bosses: Record<number, string> = {};
  for (const b of p.best_by_encounter) if (b.encounter) bosses[b.encounter.id] = b.encounter.name;
  const s = p.summary;
  return (
    <>
      <PageHeader
        eyebrow={`${c.realm || "Reino desconocido"}${c.region ? ` · ${c.region.toUpperCase()}` : ""}${c.faction ? ` · ${c.faction === "horde" ? "Horda" : "Alianza"}` : ""}`}
        title={<span style={{ color: classColor(c.class_slug) }}>{c.name}</span>}
        subtitle={
          <>
            {specLabel(c.spec)} {classLabel(c.class_slug)} — clase {CLASS_SOURCE_LABELS[c.class_source] ?? c.class_source}
            {c.guild && (
              <>
                {" · "}
                <Link href={`/guilds/${c.guild.id}`} className="text-gold-strong hover:underline">
                  &lt;{c.guild.name}&gt;
                </Link>
                {c.guild_source === "report_tag" && <span className="text-faint"> (inferida por reportes)</span>}
              </>
            )}
          </>
        }
        actions={
          <Link href={`/compare?ids=${c.id}`} className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-ink">
            Comparar con…
          </Link>
        }
      />
      <DataBanners meta={p.meta} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <StatCard label="Encuentros" value={fmtInt(s.encounters)} />
        <StatCard label="Kills" value={fmtInt(s.kills)} />
        <StatCard label="Mejor DPS" value={fmtDec(s.best_dps)} />
        <StatCard label="Mejor HPS" value={fmtDec(s.best_hps)} />
        <StatCard label="Mejor Abs/s" value={fmtDec(s.best_aps)} />
        <StatCard label="Muertes" value={fmtInt(s.deaths)} />
        <StatCard label="Interr. · Dispels" value={`${fmtInt(s.interrupts)} · ${fmtInt(s.dispels)}`} />
      </div>
      <p className="mt-2 text-xs text-faint">
        Visto por primera vez el {fmtDate(c.first_seen_at)}; última actividad {fmtDate(c.last_seen_at)}.
      </p>
      <Card title="Mejores marcas por jefe" className="mt-4">
        <BestTable rows={p.best_by_encounter} />
      </Card>
      <Card title="Equipo y línea de tiempo por pelea" className="mt-4">
        <ProfileLoadout characterId={c.id} fights={p.recent_fights} dataset={dataset} />
      </Card>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Evolución histórica">
          <EvolutionChart points={p.evolution} bosses={bosses} />
        </Card>
        <Card title="Combates recientes" actions={<Link href={`/players/${c.id}/fights`} className="text-xs text-gold-strong underline">Historial completo</Link>}>
          <RecentFights fights={p.recent_fights} />
        </Card>
      </div>
    </>
  );
}
