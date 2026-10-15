/** Formateo consistente (es-AR): miles con punto, decimales con coma. */

const LOCALE = "es-AR";

const intFmt = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const oneDec = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const compactFmt = new Intl.NumberFormat(LOCALE, { notation: "compact", maximumFractionDigits: 1 });
const dateFmt = new Intl.DateTimeFormat(LOCALE, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });
const dateTimeFmt = new Intl.DateTimeFormat(LOCALE, {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
});

type Num = number | string | null | undefined;

function toNumber(v: Num): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function fmtInt(v: Num): string {
  const n = toNumber(v);
  return n === null ? "—" : intFmt.format(Math.round(n));
}

export function fmtDec(v: Num): string {
  const n = toNumber(v);
  return n === null ? "—" : oneDec.format(n);
}

export function fmtCompact(v: Num): string {
  const n = toNumber(v);
  return n === null ? "—" : compactFmt.format(n);
}

export function fmtPct(v: Num, digits = 1): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return `${new Intl.NumberFormat(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n)} %`;
}

/** Duración en ms → "m:ss" o "h:mm:ss". */
export function fmtDuration(ms: Num): string {
  const n = toNumber(ms);
  if (n === null) return "—";
  const total = Math.round(n / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : dateFmt.format(d);
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : `${dateTimeFmt.format(d)} UTC`;
}

export function fmtBytes(v: Num): string {
  const n = toNumber(v);
  if (n === null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${oneDec.format(n / 1024)} KB`;
  return `${oneDec.format(n / (1024 * 1024))} MB`;
}

/** Formatea un valor de métrica según su tipo. */
export function fmtMetric(metric: string, v: Num): string {
  if (["deaths", "interrupts", "dispels", "killing_blows"].includes(metric)) return fmtInt(v);
  if (metric === "survival_pct") return fmtPct(v);
  if (["dps", "hps", "aps", "dtps"].includes(metric)) return fmtDec(v);
  return fmtInt(v);
}

export const DIFFICULTY_NOTE =
  "ID de dificultad tal como lo escribe el cliente en ENCOUNTER_START (Blizzard no publicó la tabla para Forever).";

export function partitionLabel(difficultyId: Num, groupSize: Num): string {
  const d = toNumber(difficultyId);
  const g = toNumber(groupSize);
  return `${g ?? "?"} jugadores · dif. ${d ?? "?"}`;
}
