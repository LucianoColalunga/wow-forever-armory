"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ClientApiError, clientGet } from "@/lib/client-api";
import { fmtDate, partitionLabel } from "@/lib/format";
import type { Dataset, FightSummary, Participant } from "@/lib/types";

import { PlayerLoadout } from "./PlayerLoadout";

interface EncounterLoadout {
  fight: FightSummary;
  performance: Participant;
}

/** Selector de pelea + equipo y línea de tiempo del personaje en esa pelea. */
export function ProfileLoadout({
  characterId,
  fights,
  dataset,
}: {
  characterId: number;
  fights: FightSummary[];
  dataset: Dataset;
}) {
  const options = fights.filter((f) => f.kind === "encounter");
  const [fightId, setFightId] = useState<number | null>(options[0]?.id ?? null);
  const [data, setData] = useState<EncounterLoadout | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (fightId === null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    clientGet<EncounterLoadout>(`/players/${characterId}/encounters/${fightId}`, { dataset })
      .then((d) => !cancelled && setData(d))
      .catch((e: unknown) => !cancelled && setError(e instanceof ClientApiError ? e.message : "No se pudo cargar."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [characterId, fightId, dataset]);

  if (options.length === 0) {
    return <p className="text-sm text-muted">Todavía no hay peleas contra jefes para este personaje.</p>;
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-muted">Pelea</span>
          <select
            value={fightId ?? ""}
            onChange={(e) => setFightId(Number(e.target.value))}
            className="max-w-xs rounded-md border border-line bg-surface px-2 py-1"
          >
            {options.map((f) => (
              <option key={f.id} value={f.id}>
                {f.encounter?.name ?? "Jefe"} · {f.success ? "kill" : "wipe"} · {fmtDate(f.start_at)}
              </option>
            ))}
          </select>
        </label>
        {data && (
          <Link href={`/encounters/${data.fight.id}`} className="text-xs text-gold-strong hover:underline">
            Ver combate completo ({partitionLabel(data.fight.difficulty_id, data.fight.group_size)}) →
          </Link>
        )}
      </div>
      {loading && (
        <p className="text-sm text-muted" role="status">
          Cargando…
        </p>
      )}
      {error && (
        <p className="text-sm text-danger" role="alert">
          {error}
        </p>
      )}
      {data && !loading && (
        <PlayerLoadout participant={data.performance} durationMs={data.fight.duration_ms} isDemo={data.fight.dataset === "demo"} />
      )}
    </div>
  );
}
