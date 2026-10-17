"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

export interface FilterOption {
  value: string;
  label: string;
}

export interface FilterDef {
  name: string;
  label: string;
  type: "select" | "date" | "search";
  placeholder?: string;
  options?: FilterOption[];
  /** Valor actual efectivo (puede venir de un default del servidor). */
  value: string;
  help?: string;
}

/** Campo de texto que actualiza la URL al dejar de escribir (o con Enter). Mínimo 2 caracteres. */
function SearchField({
  id,
  value,
  placeholder,
  onCommit,
}: {
  id: string;
  value: string;
  placeholder?: string;
  onCommit: (v: string) => void;
}) {
  const [text, setText] = useState(value);
  const last = useRef(value);
  const commit = useRef(onCommit);
  commit.current = onCommit;
  useEffect(() => {
    setText(value);
    last.current = value;
  }, [value]);
  useEffect(() => {
    const v = text.trim();
    if (v === last.current || (v.length > 0 && v.length < 2)) return;
    const t = setTimeout(() => {
      last.current = v;
      commit.current(v);
    }, 450);
    return () => clearTimeout(t);
  }, [text]);
  return (
    <input
      id={id}
      type="search"
      value={text}
      maxLength={24}
      placeholder={placeholder}
      autoComplete="off"
      onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => {
        const v = text.trim();
        if (e.key === "Enter" && v !== last.current && (v.length === 0 || v.length >= 2)) {
          last.current = v;
          onCommit(v);
        }
      }}
      className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm"
    />
  );
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
            ) : f.type === "search" ? (
              <SearchField id={id} value={f.value} placeholder={f.placeholder} onCommit={(v) => update(f.name, v)} />
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
