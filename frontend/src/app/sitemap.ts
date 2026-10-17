import type { MetadataRoute } from "next";

import { apiGet } from "@/lib/api";
import { siteUrl } from "@/lib/site";
import type { Character, Paged } from "@/lib/types";

// Se regenera cada hora; si la API no responde, se publican sólo las páginas fijas.
export const revalidate = 3600;

const STATIC_PATHS = [
  "/",
  "/rankings/pvp",
  "/rankings/pve",
  "/players",
  "/guilds",
  "/encounters",
  "/raids",
  "/dungeons",
  "/methodology",
  "/sources",
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();
  const entries: MetadataRoute.Sitemap = STATIC_PATHS.map((path) => ({
    url: `${base}${path}`,
    changeFrequency: path.startsWith("/rankings") ? "daily" : "weekly",
    priority: path === "/" ? 1 : path.startsWith("/rankings") ? 0.9 : 0.6,
  }));
  try {
    // Sólo datos reales: el conjunto demo es sintético y no se indexa.
    const players = await apiGet<Paged<Character>>("/players", { dataset: "real", page_size: 100, sort: "last_seen" });
    for (const p of players.items) {
      entries.push({
        url: `${base}/players/${p.id}`,
        lastModified: p.last_seen_at ?? undefined,
        changeFrequency: "weekly",
        priority: 0.5,
      });
    }
  } catch {
    /* API dormida o caída: el sitemap igual sirve con las páginas fijas */
  }
  return entries;
}
