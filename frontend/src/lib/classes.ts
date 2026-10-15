/** Etiquetas y colores de clases (paleta propia, contraste ≥ 4,5:1 sobre el fondo). */

export const CLASS_INFO: Record<string, { label: string; color: string }> = {
  warrior: { label: "Guerrero", color: "#d2a77a" },
  paladin: { label: "Paladín", color: "#f39cc4" },
  hunter: { label: "Cazador", color: "#afd77a" },
  rogue: { label: "Pícaro", color: "#f4e273" },
  priest: { label: "Sacerdote", color: "#f2f2f2" },
  shaman: { label: "Chamán", color: "#6aa9f2" },
  mage: { label: "Mago", color: "#6fd3f2" },
  warlock: { label: "Brujo", color: "#ab9bf5" },
  druid: { label: "Druida", color: "#ff9a45" },
};

export const SPEC_LABELS: Record<string, string> = {
  arms: "Armas",
  fury: "Furia",
  protection: "Protección",
  holy: "Sagrado",
  retribution: "Reprensión",
  "beast-mastery": "Bestias",
  marksmanship: "Puntería",
  survival: "Supervivencia",
  assassination: "Asesinato",
  combat: "Combate",
  subtlety: "Sutileza",
  discipline: "Disciplina",
  shadow: "Sombra",
  elemental: "Elemental",
  enhancement: "Mejora",
  restoration: "Restauración",
  arcane: "Arcano",
  fire: "Fuego",
  frost: "Escarcha",
  affliction: "Aflicción",
  demonology: "Demonología",
  destruction: "Destrucción",
  balance: "Equilibrio",
  feral: "Feral",
};

export const CLASS_SPECS: Record<string, string[]> = {
  warrior: ["arms", "fury", "protection"],
  paladin: ["holy", "protection", "retribution"],
  hunter: ["beast-mastery", "marksmanship", "survival"],
  rogue: ["assassination", "combat", "subtlety"],
  priest: ["discipline", "holy", "shadow"],
  shaman: ["elemental", "enhancement", "restoration"],
  mage: ["arcane", "fire", "frost"],
  warlock: ["affliction", "demonology", "destruction"],
  druid: ["balance", "feral", "restoration"],
};

export const ROLE_LABELS: Record<string, string> = { dps: "Daño", healer: "Sanador", tank: "Tanque" };

export const CLASS_SOURCE_LABELS: Record<string, string> = {
  combatant_info: "detectada en COMBATANT_INFO",
  signature: "inferida por hechizos",
  role: "inferida por rol (confianza baja)",
  admin: "corregida por un admin",
  unknown: "sin detectar",
};

export function classColor(slug: string | null | undefined): string {
  return (slug && CLASS_INFO[slug]?.color) || "#b0a796";
}

export function classLabel(slug: string | null | undefined): string {
  return (slug && CLASS_INFO[slug]?.label) || "Clase desconocida";
}

export function specLabel(spec: string | null | undefined): string {
  return (spec && SPEC_LABELS[spec]) || "—";
}
