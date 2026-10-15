"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

export interface FilterOption {
  value: string;
  label: string;
}

export interface FilterDef {
  name: string;
  label: string;
  type: "select" | "date";
  options?: FilterOption[];
  /** Valor actual efectivo (puede venir de un default del servidor). */
  value: string;
  help?: string;
}

/** Filtros que viven en la URL: compartibles, navegables con atrás/adelante y accesibles por teclado. */
export function FilterBar({ filters, resetKeys = [] }: { filters: FilterDef[]; resetKeys?: string[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, start] = useTransition();

  function update(name: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(name, value);
    else next.delete(name);
    next.delete("page");
    // Al cambiar la clase se limpian los filtros dependientes (p. ej. la spec).
    if (name === "class") for (const k of resetKeys) next.delete(k);
    start(() => router.replace(`${pathname}?${next.toString()}`, { scroll: false }));
  }

  return (
    <form
      className="card mb-4 grid grid-cols-2 gap-3 p-3 sm:grid-cols-3 lg:grid-cols-6"
      aria-label="Filtros"
      aria-busy={pending}
      onSubmit={(e) => e.preventDefault()}
    >
      {filters.map((f) => {
        const id = `filter-${f.name}`;
        return (
          <div key={f.name} className="flex flex-col gap-1">
            <label htmlFor={id} className="text-xs text-muted">
              {f.label}
            </label>
            {f.type === "select" ? (
              <select
                id={id}
                value={f.value}
                onChange={(e) => update(f.name, e.target.value)}
                className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm"
                aria-describedby={f.help ? `${id}-help` : undefined}
              >
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={id}
                type="date"
                value={f.value}
                onChange={(e) => update(f.name, e.target.value)}
                className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm"
              />
            )}
            {f.help && (
              <span id={`${id}-help`} className="text-[11px] text-faint">
                {f.help}
              </span>
            )}
          </div>
        );
      })}
      {pending && (
        <span className="col-span-full text-xs text-arcane" role="status">
          Actualizando…
        </span>
      )}
    </form>
  );
}
