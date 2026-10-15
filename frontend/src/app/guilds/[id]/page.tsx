import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Card, DataBanners, ErrorState, PageHeader, StatCard } from "@/components/ui";
import { GuildActivity, ProgressionTable, type ProgressionRow } from "@/components/views/GuildViews";
import { PlayerList } from "@/components/views/PlayerList";
import { ApiError, apiGet } from "@/lib/api";
import { getDataset } from "@/lib/dataset";
import { fmtDate, fmtInt } from "@/lib/format";
import type { Character, DataMeta } from "@/lib/types";

export const metadata: Metadata = { title: "Hermandad" };

interface GuildProfile {
  guild: { id: number; name: string; realm: string; region: string; faction: string | null; dataset: string };
  members: Character[];
  reports: { public_id: string; title: string; created_at: string; log_started_at: string | null; stats: Record<string, number> | null }[];
  progression: ProgressionRow[];
  activity: { week: string; pulls: number; kills: number }[];
  meta: DataMeta;
}

export default async function GuildPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const dataset = await getDataset(await searchParams);
  let g: GuildProfile;
  try {
    g = await apiGet<GuildProfile>(`/guilds/${id}`, { dataset });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ErrorState message={e instanceof ApiError ? e.message : "Error inesperado."} retryHref={`/guilds/${id}`} />;
  }
  const kills = g.progression.reduce((a, p) => a + p.kills, 0);
  return (
    <>
      <PageHeader
        eyebrow={`${g.guild.realm || "Reino ?"}${g.guild.region ? ` · ${g.guild.region.toUpperCase()}` : ""}${g.guild.faction ? ` · ${g.guild.faction === "horde" ? "Horda" : "Alianza"}` : ""}`}
        title={`<${g.guild.name}>`}
        subtitle="La membresía se infiere de los reportes etiquetados con la hermandad salvo que un admin la haya confirmado."
      />
      <DataBanners meta={g.meta} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Miembros vistos" value={fmtInt(g.members.length)} />
        <StatCard label="Reportes" value={fmtInt(g.reports.length)} />
        <StatCard label="Jefes derrotados" value={fmtInt(g.progression.length)} />
        <StatCard label="Kills totales" value={fmtInt(kills)} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Progreso">
          <ProgressionTable rows={g.progression} />
        </Card>
        <Card title="Evolución">
          <GuildActivity weeks={g.activity} />
        </Card>
      </div>
      <Card title="Miembros" className="mt-4">
        <PlayerList players={g.members} showMembership />
      </Card>
      <Card title="Reportes recientes" className="mt-4">
        <ul className="divide-y divide-line/70 text-sm">
          {g.reports.map((r) => (
            <li key={r.public_id} className="flex flex-wrap justify-between gap-2 py-2">
              <Link href={`/reports/${r.public_id}`} className="text-ink hover:text-gold-strong">
                {r.title}
              </Link>
              <span className="text-xs text-muted">
                {fmtDate(r.log_started_at)} · {fmtInt(r.stats?.kills ?? 0)} kills
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
