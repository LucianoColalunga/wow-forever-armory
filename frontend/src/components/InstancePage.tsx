import Link from "next/link";

import { fmtDateTime, fmtDuration, fmtInt } from "@/lib/format";
import type { DataMeta, Encounter, FightSummary, Instance } from "@/lib/types";

import { FightList } from "./views/FightList";
import { Badge, Card, DataBanners, EmptyState, PageHeader } from "./ui";

export interface InstancePayload {
  instance: Instance;
  bosses: (Encounter & { pulls: number; kills: number; fastest_kill_ms: number | null; last_seen_at: string | null })[];
  recent_fights: FightSummary[];
  runs?: FightSummary[];
  runs_note?: string;
  meta: DataMeta;
}

const KIND_LABEL = { raid: "Banda", dungeon: "Mazmorra", battleground: "Campo de batalla" } as const;

export function InstancePage({ data }: { data: InstancePayload }) {
  const inst = data.instance;
  return (
    <>
      <PageHeader
        eyebrow={`${KIND_LABEL[inst.kind]}${inst.is_new ? " · nueva en Forever" : ""}`}
        title={inst.name}
        subtitle={[
          inst.max_players ? `Hasta ${inst.max_players} jugadores` : null,
          inst.level_range ? `Nivel ${inst.level_range}` : null,
          inst.notes || null,
        ]
          .filter(Boolean)
          .join(" · ")}
        actions={
          <div className="flex flex-col items-end gap-1">
            <Badge status={inst.verification} />
            <a href={inst.source_url} className="text-xs text-muted underline hover:text-ink" rel="noreferrer noopener" target="_blank">
              Fuente
            </a>
          </div>
        }
      />
      <DataBanners meta={data.meta} />
      <Card title="Jefes registrados">
        {data.bosses.length === 0 ? (
          <EmptyState title="Sin jefes registrados todavía">
            Los jefes se crean a partir de los combat logs importados (evento ENCOUNTER_START). No se inventan nombres ni
            IDs: aparecerán cuando alguien suba un log de esta instancia.
          </EmptyState>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.bosses.map((b) => (
              <li key={b.id} className="rounded-lg border border-line p-3">
                <p className="font-medium text-ink">{b.name}</p>
                <p className="mt-1 text-xs text-muted">
                  {fmtInt(b.kills)} kills · {fmtInt(b.pulls)} intentos · récord {fmtDuration(b.fastest_kill_ms)}
                </p>
                <p className="text-xs text-faint">Último: {fmtDateTime(b.last_seen_at)}</p>
                <div className="mt-2 flex gap-3 text-sm">
                  <Link href={`/rankings/pve/bosses/${b.id}`} className="text-gold-strong hover:underline">
                    Ranking
                  </Link>
                  <Link href={`/encounters?boss_id=${b.id}`} className="text-muted hover:text-ink hover:underline">
                    Historial
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {data.runs && (
        <Card title="Recorridos registrados" className="mt-4">
          <p className="mb-2 text-xs text-faint">{data.runs_note}</p>
          <FightList fights={data.runs} />
        </Card>
      )}
      <Card title="Combates recientes" className="mt-4">
        <FightList fights={data.recent_fights} />
      </Card>
    </>
  );
}

export function InstanceGrid({ items, base }: { items: Instance[]; base: "raids" | "dungeons" }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((i) => (
        <li key={i.id}>
          <Link href={`/${base}/${i.slug}`} className="card block h-full p-4 transition-colors hover:border-gold">
            <div className="flex items-start justify-between gap-2">
              <span className="font-display text-lg text-ink">{i.name}</span>
              <Badge status={i.verification} />
            </div>
            <p className="mt-1 text-xs text-muted">
              {i.max_players ? `${i.max_players} jugadores` : ""}
              {i.level_range ? ` · nivel ${i.level_range}` : ""}
              {i.is_new ? " · nueva en Forever" : " · clásica"}
            </p>
            {i.notes && <p className="mt-2 text-xs text-faint">{i.notes}</p>}
          </Link>
        </li>
      ))}
    </ul>
  );
}
