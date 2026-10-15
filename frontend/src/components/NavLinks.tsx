"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/rankings/pve", label: "Rankings PvE" },
  { href: "/rankings/pvp", label: "Rankings PvP" },
  { href: "/raids", label: "Bandas" },
  { href: "/dungeons", label: "Mazmorras" },
  { href: "/players", label: "Personajes" },
  { href: "/guilds", label: "Hermandades" },
  { href: "/encounters", label: "Historial" },
  { href: "/compare", label: "Comparar" },
  { href: "/import", label: "Importar" },
];

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav aria-label="Secciones" className="mx-auto max-w-7xl overflow-x-auto px-4 [scrollbar-width:thin]">
      <ul className="flex gap-1 pb-2 text-sm">
        {LINKS.map((l) => {
          const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
          return (
            <li key={l.href}>
              <Link
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`block whitespace-nowrap rounded-md px-3 py-1.5 transition-colors ${
                  active ? "bg-surface-2 text-gold-strong" : "text-muted hover:bg-surface hover:text-ink"
                }`}
              >
                {l.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
