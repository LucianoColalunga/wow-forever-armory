"use client";

import Link from "next/link";

import { classLabel, specLabel } from "@/lib/classes";
import { fmtDate, fmtInt } from "@/lib/format";
import type { Character } from "@/lib/types";

import { type Column, DataTable } from "../DataTable";
import { ClassName } from "../ui";

export function PlayerList({ players, showMembership = false }: { players: Character[]; showMembership?: boolean }) {
  const columns: Column<Character>[] = [
    {
      key: "name",
      label: "Personaje",
      sortValue: (c) => c.name,
      render: (c) => <ClassName name={c.name} classSlug={c.class_slug} spec={c.spec} realm={c.realm} href={`/players/${c.id}`} />,
    },
    {
      key: "class",
      label: "Clase · spec",
      sortValue: (c) => `${c.class_slug ?? "zz"}-${c.spec ?? ""}`,
      render: (c) => (
        <span className="text-xs text-muted">
          {classLabel(c.class_slug)} · {specLabel(c.spec)}
        </span>
      ),
    },
    {
      key: "guild",
      label: "Hermandad",
      sortValue: (c) => c.guild?.name ?? "",
      render: (c) =>
        c.guild ? (
          <Link href={`/guilds/${c.guild.id}`} className="text-sm text-muted hover:text-ink">
            {c.guild.name}
          </Link>
        ) : (
          <span className="text-faint">—</span>
        ),
    },
  ];
  if (showMembership) {
    columns.push({ key: "membership", label: "Pertenencia", render: (c) => <span className="text-xs text-faint">{c.membership}</span> });
  } else {
    columns.push({ key: "fights", label: "Combates", align: "right", sortValue: (c) => c.fights ?? 0, render: (c) => fmtInt(c.fights) });
  }
  columns.push({
    key: "seen",
    label: "Última actividad",
    sortValue: (c) => c.last_seen_at ?? "",
    render: (c) => <span className="text-xs text-muted">{fmtDate(c.last_seen_at)}</span>,
  });
  return (
    <DataTable
      columns={columns}
      rows={players}
      rowKey={(c) => c.id}
      caption="Personajes"
      filterText={(c) => `${c.name} ${c.realm} ${c.guild?.name ?? ""}`}
      emptyMessage="No hay personajes."
    />
  );
}
