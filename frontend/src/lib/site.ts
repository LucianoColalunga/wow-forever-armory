/** URL pública del sitio (para metadatos, sitemap y URLs canónicas). */
export function siteUrl(): string {
  const host = process.env.CANONICAL_HOST?.trim().toLowerCase();
  if (host) return `https://${host}`;
  const explicit = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (explicit) return explicit.replace(/\/$/, "");
  return "http://localhost:3000";
}

export const SITE_NAME = "WoW Forever Armory";
