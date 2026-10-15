import Link from "next/link";

import type { Dataset } from "@/lib/types";

import { DatasetToggle } from "./DatasetToggle";
import { Logo } from "./Logo";
import { NavLinks } from "./NavLinks";
import { UserMenu } from "./UserMenu";

export function SiteHeader({ dataset }: { dataset: Dataset }) {
  return (
    <header className="z-40 border-b border-line bg-bg/95 sm:sticky sm:top-0 sm:backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
        <Link href="/" className="flex items-center gap-2" aria-label="Inicio de WoW Forever Armory">
          <Logo />
          <span className="leading-tight">
            <span className="block font-display text-base tracking-wide text-gold-strong">Forever Armory</span>
            <span className="block text-[11px] uppercase tracking-[0.18em] text-faint">Competitive Analytics</span>
          </span>
        </Link>
        <form action="/search" method="get" role="search" className="order-3 w-full sm:order-none sm:ml-4 sm:w-64">
          <label htmlFor="global-search" className="sr-only">
            Buscar personajes, hermandades, jefes o reportes
          </label>
          <input
            id="global-search"
            name="q"
            type="search"
            minLength={2}
            maxLength={64}
            placeholder="Buscar personaje, hermandad, jefe…"
            className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-sm placeholder:text-faint"
          />
        </form>
        <div className="ml-auto flex items-center gap-3">
          <DatasetToggle dataset={dataset} />
          <UserMenu />
        </div>
      </div>
      <NavLinks />
    </header>
  );
}
