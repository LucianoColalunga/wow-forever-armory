"use client";

import { type ReactNode, useId, useMemo, useState } from "react";

export interface Column<T> {
  key: string;
  label: string;
  /** Valor para ordenar; si falta, la columna no es ordenable. */
  sortValue?: (row: T) => number | string | null | undefined;
  render: (row: T) => ReactNode;
  align?: "left" | "right";
  title?: string;
  className?: string;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  caption: string;
  initialSort?: { key: string; dir: "asc" | "desc" };
  /** Texto contra el que filtra el buscador local; sin esta función no se muestra el filtro. */
  filterText?: (row: T) => string;
  emptyMessage?: string;
  highlight?: (row: T) => boolean;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  initialSort,
  filterText,
  emptyMessage = "No hay datos para mostrar.",
  highlight,
}: Props<T>) {
  const [sort, setSort] = useState(initialSort);
  const [query, setQuery] = useState("");
  const filterId = useId();

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q && filterText ? rows.filter((r) => filterText(r).toLowerCase().includes(q)) : rows;
    if (!sort) return filtered;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return filtered;
    const get = col.sortValue;
    return [...filtered].sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      const cmp = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb), "es");
      return sort.dir === "asc" ? cmp : -cmp;
    });
  }, [rows, sort, query, columns, filterText]);

  function toggle(key: string) {
    setSort((s) => (s?.key === key ? { key, dir: s.dir === "desc" ? "asc" : "desc" } : { key, dir: "desc" }));
  }

  return (
    <div>
      {filterText && (
        <div className="mb-2 flex items-center gap-2">
          <label htmlFor={filterId} className="text-xs text-muted">
            Filtrar esta página
          </label>
          <input
            id={filterId}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Nombre, hermandad…"
            className="w-56 rounded-md border border-line bg-surface px-2 py-1 text-sm"
          />
          {query && (
            <span className="text-xs text-faint" aria-live="polite">
              {visible.length} de {rows.length}
            </span>
          )}
        </div>
      )}
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-surface-2 text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              {columns.map((c) => {
                const active = sort?.key === c.key;
                const ariaSort = active ? (sort?.dir === "asc" ? "ascending" : "descending") : "none";
                return (
                  <th
                    key={c.key}
                    scope="col"
                    aria-sort={c.sortValue ? ariaSort : undefined}
                    className={`px-3 py-2 font-medium ${c.align === "right" ? "text-right" : ""} ${c.className ?? ""}`}
                    title={c.title}
                  >
                    {c.sortValue ? (
                      <button
                        type="button"
                        onClick={() => toggle(c.key)}
                        className={`inline-flex items-center gap-1 uppercase hover:text-ink ${active ? "text-gold-strong" : ""}`}
                      >
                        {c.label}
                        <span aria-hidden="true">{active ? (sort?.dir === "asc" ? "▲" : "▼") : "↕"}</span>
                      </button>
                    ) : (
                      c.label
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-6 text-center text-muted">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              visible.map((r) => (
                <tr
                  key={rowKey(r)}
                  className={`border-t border-line/70 hover:bg-surface-2/60 ${highlight?.(r) ? "bg-gold/5" : ""}`}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={`px-3 py-2 ${c.align === "right" ? "num text-right" : ""} ${c.className ?? ""}`}>
                      {c.render(r)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
