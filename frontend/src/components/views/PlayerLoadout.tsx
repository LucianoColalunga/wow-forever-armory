"use client";

import { classColor, classLabel, specLabel } from "@/lib/classes";
import { fmtDec, fmtDuration } from "@/lib/format";
import type { GearItem, Participant } from "@/lib/types";

import { CastTimelineChart } from "../Charts";

const LEFT = ["Cabeza", "Cuello", "Hombros", "Espalda", "Pecho", "Camisa", "Tabardo", "Muñecas"];
const RIGHT = ["Manos", "Cintura", "Piernas", "Pies", "Dedo 1", "Dedo 2", "Abalorio 1", "Abalorio 2"];
const BOTTOM = ["Mano principal", "Mano secundaria", "A distancia"];

function Silhouette({ color }: { color: string }) {
  // Silueta propia (no usa modelos ni arte del juego): figura con hombreras y capa.
  return (
    <svg viewBox="0 0 120 220" className="h-full w-full" aria-hidden="true">
      <defs>
        <linearGradient id="sil-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#263248" />
          <stop offset="1" stopColor="#141a26" />
        </linearGradient>
      </defs>
      <path d="M26 58 Q60 40 94 58 L104 170 Q60 190 16 170 Z" fill="#101622" stroke={color} strokeOpacity="0.35" />
      <circle cx="60" cy="30" r="17" fill="url(#sil-body)" stroke={color} strokeWidth="2" />
      <path d="M30 56 Q60 44 90 56 L86 120 Q60 128 34 120 Z" fill="url(#sil-body)" stroke={color} strokeWidth="2" />
      <path d="M22 52 Q34 42 46 52 L42 64 Q30 66 22 60 Z M98 52 Q86 42 74 52 L78 64 Q90 66 98 60 Z" fill={color} fillOpacity="0.55" />
      <path d="M30 60 L18 116 L28 118 L38 70 Z M90 60 L102 116 L92 118 L82 70 Z" fill="url(#sil-body)" stroke={color} strokeWidth="1.5" />
      <path d="M38 120 L34 204 L54 204 L58 128 Z M82 120 L86 204 L66 204 L62 128 Z" fill="url(#sil-body)" stroke={color} strokeWidth="1.5" />
      <rect x="36" y="112" width="48" height="8" rx="2" fill={color} fillOpacity="0.4" />
      <path d="M104 110 L114 30 L118 32 L110 112 Z" fill="#9fb3c8" fillOpacity="0.6" />
    </svg>
  );
}

function SlotCard({ name, item, linkable }: { name: string; item?: GearItem; linkable: boolean }) {
  if (!item) {
    return (
      <div className="rounded-md border border-dashed border-line/70 px-2 py-1.5 text-[11px] text-faint">
        <span className="block text-muted">{name}</span>vacío
      </div>
    );
  }
  const body = (
    <>
      <span className="flex items-center justify-between gap-1 text-[11px] text-muted">
        {name}
        <span className="num rounded bg-surface-3 px-1 text-[10px] text-gold-strong" title="Nivel de objeto">
          {item.item_level}
        </span>
      </span>
      <span className="num block text-xs text-ink">#{item.item_id}</span>
      {(item.enchants.length > 0 || item.gems.length > 0) && (
        <span className="block text-[10px] text-arcane">
          {item.enchants.length > 0 ? "encantado" : ""}
          {item.enchants.length > 0 && item.gems.length > 0 ? " · " : ""}
          {item.gems.length > 0 ? `${item.gems.length} gema${item.gems.length > 1 ? "s" : ""}` : ""}
        </span>
      )}
    </>
  );
  return linkable ? (
    <a
      href={`https://www.wowhead.com/forever/item=${item.item_id}`}
      target="_blank"
      rel="noreferrer noopener"
      className="block rounded-md border border-line bg-surface-2/70 px-2 py-1.5 hover:border-arcane"
      title={`Ver el objeto ${item.item_id} en Wowhead (sitio externo)`}
    >
      {body}
    </a>
  ) : (
    <div className="rounded-md border border-line bg-surface-2/70 px-2 py-1.5">{body}</div>
  );
}

export function GearDoll({
  gear,
  classSlug,
  spec,
  name,
  avgItemLevel,
  linkable,
}: {
  gear: GearItem[] | null | undefined;
  classSlug: string | null;
  spec: string | null;
  name: string;
  avgItemLevel?: number | null;
  linkable: boolean;
}) {
  if (!gear || gear.length === 0) {
    return (
      <p className="text-sm text-muted">
        El log no trae equipo para esta pelea. El cliente lo escribe al empezar cada jefe con Advanced Combat Logging
        activado (no en campos de batalla ni fuera de encuentros).
      </p>
    );
  }
  const bySlot = new Map(gear.map((g) => [g.slot_name, g]));
  const known = gear.every((g) => !g.slot_name.startsWith("Ranura"));
  const color = classColor(classSlug);
  if (!known) {
    return (
      <ul className="grid gap-2 sm:grid-cols-3">
        {gear.map((g) => (
          <li key={g.slot}>
            <SlotCard name={g.slot_name} item={g} linkable={linkable} />
          </li>
        ))}
      </ul>
    );
  }
  return (
    <figure className="m-0" aria-label={`Equipo de ${name}`}>
      <div className="grid grid-cols-[1fr_minmax(90px,140px)_1fr] gap-2 sm:gap-3">
        <div className="space-y-1.5">
          {LEFT.map((s) => (
            <SlotCard key={s} name={s} item={bySlot.get(s)} linkable={linkable} />
          ))}
        </div>
        <div className="flex flex-col items-center justify-center gap-2">
          <div className="h-56 w-full">
            <Silhouette color={color} />
          </div>
          <div className="text-center">
            <p className="font-medium" style={{ color }}>
              {name}
            </p>
            <p className="text-[11px] text-muted">
              {specLabel(spec)} · {classLabel(classSlug)}
            </p>
            {avgItemLevel ? (
              <p className="num mt-1 text-sm text-gold-strong" title="Nivel de objeto promedio (sin camisa ni tabardo)">
                Nv. {fmtDec(avgItemLevel)}
              </p>
            ) : null}
          </div>
        </div>
        <div className="space-y-1.5">
          {RIGHT.map((s) => (
            <SlotCard key={s} name={s} item={bySlot.get(s)} linkable={linkable} />
          ))}
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2">
        {BOTTOM.map((s) => (
          <SlotCard key={s} name={s} item={bySlot.get(s)} linkable={linkable} />
        ))}
      </div>
      <figcaption className="mt-2 text-[11px] text-faint">
        Objetos según COMBATANT_INFO al inicio del encuentro (ID y nivel de objeto; el log no trae nombres ni apariencia).
        {linkable ? " Cada ranura abre el objeto en Wowhead." : " Datos DEMO: los IDs de objeto son ficticios."}
      </figcaption>
    </figure>
  );
}

/** Equipo + línea de tiempo de lanzamientos de un jugador en una pelea. */
export function PlayerLoadout({
  participant,
  durationMs,
  isDemo,
}: {
  participant: Participant;
  durationMs: number;
  isDemo: boolean;
}) {
  const casts = participant.casts;
  const castCount = casts?.t.length ?? 0;
  const cpm = durationMs > 0 ? (castCount * 60000) / durationMs : 0;
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <section aria-label="Equipo">
        <h3 className="mb-2 font-display text-base">Equipo en esta pelea</h3>
        <GearDoll
          gear={participant.gear}
          classSlug={participant.class_slug}
          spec={participant.spec}
          name={participant.name}
          avgItemLevel={participant.avg_item_level}
          linkable={!isDemo}
        />
      </section>
      <section aria-label="Línea de tiempo de lanzamientos">
        <h3 className="mb-2 font-display text-base">Qué usó en cada momento</h3>
        {casts && castCount > 0 ? (
          <>
            <p className="mb-2 text-xs text-muted">
              {castCount} lanzamientos en {fmtDuration(durationMs)} · {fmtDec(cpm)} por minuto
            </p>
            <CastTimelineChart
              title={`Lanzamientos de ${participant.name}`}
              description="Cada punto es un hechizo lanzado (SPELL_CAST_SUCCESS); los más usados arriba."
              data={casts}
              durationMs={durationMs}
            />
          </>
        ) : (
          <p className="text-sm text-muted">No hay lanzamientos registrados para este jugador en esta pelea.</p>
        )}
      </section>
    </div>
  );
}
