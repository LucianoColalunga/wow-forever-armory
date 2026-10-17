import Link from "next/link";

import { fmtDate, fmtDec, fmtInt } from "@/lib/format";
import type { Instance } from "@/lib/types";

export interface Position {
  position: number;
  of: number;
}

export interface PvpProfileRow {
  battleground: Instance | null;
  matches: number;
  best_damage_to_players: number | null;
  best_dps: number | null;
  best_hps: number | null;
  killing_blows: number;
  deaths: number;
  last_match_at: string | null;
  damage_position: Position | null;
  hps_position: Position | null;
}

export function PositionTag({ pos, href }: { pos: Position | null | undefined; href?: string }) {
  if (!pos) return <span className="text-faint">—</span>;
  const top = pos.position <= 3;
  const body = (
    <span className={`num text-xs ${top ? "text-gold-strong" : "text-muted"}`} title={`Puesto ${pos.position} de ${pos.of} personajes`}>
      #{pos.position}
      <span className="text-faint"> / {pos.of}</span>
    </span>
  );
  return href ? (
    <Link href={href} className="hover:underline">
      {body}
    </Link>
  ) : (
    body
  );
}

/** Rendimiento PvP del personaje por campo de batalla, con su puesto en el ranking de pico. */
export function PlayerPvp({ rows, name }: { rows: PvpProfileRow[]; name: string }) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted">Sin partidas de campo de batalla registradas para este personaje.</p>;
  }
  const q = encodeURIComponent(name.slice(0, 24));
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">Rendimiento PvP por campo de batalla</caption>
        <thead>
          <tr className="text-left text-xs text-muted">
            <th scope="col" className="py-1.5 pr-3 font-normal">Campo de batalla</th>
            <th scope="col" className="py-1.5 pr-3 text-right font-normal">Partidas</th>
            <th scope="col" className="py-1.5 pr-3 text-right font-normal">Mejor daño a jugadores</th>
            <th scope="col" className="py-1.5 pr-3 text-right font-normal">Mejor HPS</th>
            <th scope="col" className="py-1.5 pr-3 text-right font-normal">Golpes de gracia</th>
            <th scope="col" className="py-1.5 pr-3 text-right font-normal">Muertes</th>
            <th scope="col" className="py-1.5 font-normal">Última</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const slug = r.battleground?.slug ?? "";
            const base = `/rankings/pvp?battleground=${slug}&q=${q}`;
            return (
              <tr key={slug || "x"} className="border-t border-line/60">
                <td className="py-1.5 pr-3">{r.battleground?.name ?? "Desconocido"}</td>
                <td className="num py-1.5 pr-3 text-right">{fmtInt(r.matches)}</td>
                <td className="num py-1.5 pr-3 text-right">
                  {fmtInt(r.best_damage_to_players)}{" "}
                  <PositionTag pos={r.damage_position} href={`${base}&metric=damage_to_players`} />
                </td>
                <td className="num py-1.5 pr-3 text-right">
                  {r.best_hps ? fmtDec(r.best_hps) : "—"} <PositionTag pos={r.hps_position} href={`${base}&metric=hps`} />
                </td>
                <td className="num py-1.5 pr-3 text-right">{fmtInt(r.killing_blows)}</td>
                <td className="num py-1.5 pr-3 text-right">{fmtInt(r.deaths)}</td>
                <td className="py-1.5 text-xs text-muted">{fmtDate(r.last_match_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-faint">
        Puesto = posición en el ranking de pico (mejor partida de cada personaje). Los logs de campo de batalla sólo registran lo
        que pasa cerca de quien graba: las cifras son parciales.
      </p>
    </div>
  );
}
