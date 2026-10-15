import { CLASS_INFO, CLASS_SPECS, ROLE_LABELS, SPEC_LABELS } from "./classes";
import type { FilterOption } from "@/components/FilterBar";

export const METRIC_LABELS: Record<string, string> = {
  dps: "DPS",
  hps: "HPS efectivo",
  aps: "Absorciones/s",
  damage_done: "Daño total",
  healing_effective: "Curación efectiva total",
  absorbs_provided: "Absorciones totales",
  damage_taken: "Daño recibido",
  dtps: "Daño recibido/s",
  deaths: "Muertes",
  survival_pct: "Supervivencia",
  interrupts: "Interrupciones",
  dispels: "Dispels",
  damage_to_players: "Daño a jugadores",
  killing_blows: "Golpes de gracia",
};

export const METHOD_OPTIONS: FilterOption[] = [
  { value: "peak", label: "A · Pico" },
  { value: "consistency", label: "B · Consistencia" },
  { value: "percentile", label: "C · Percentil" },
];

export function metricOptions(keys: string[]): FilterOption[] {
  return keys.map((k) => ({ value: k, label: METRIC_LABELS[k] ?? k }));
}

export function classOptions(): FilterOption[] {
  return [{ value: "", label: "Todas" }, ...Object.entries(CLASS_INFO).map(([k, v]) => ({ value: k, label: v.label }))];
}

export function specOptions(classSlug: string | undefined): FilterOption[] {
  const specs = classSlug ? (CLASS_SPECS[classSlug] ?? []) : [];
  return [{ value: "", label: classSlug ? "Todas" : "Elegí una clase" }, ...specs.map((s) => ({ value: s, label: SPEC_LABELS[s] ?? s }))];
}

export function roleOptions(): FilterOption[] {
  return [{ value: "", label: "Todos" }, ...Object.entries(ROLE_LABELS).map(([k, v]) => ({ value: k, label: v }))];
}

export function seasonOptions(seasons: { id: number; name: string }[]): FilterOption[] {
  return [{ value: "", label: "Todo el período" }, ...seasons.map((s) => ({ value: String(s.id), label: s.name }))];
}
