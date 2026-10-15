import type { Metadata, Viewport } from "next";
import { Cinzel, Inter } from "next/font/google";
import Link from "next/link";
import type { ReactNode } from "react";

import { SiteHeader } from "@/components/SiteHeader";
import { getDataset } from "@/lib/dataset";

import "./globals.css";

const cinzel = Cinzel({ subsets: ["latin"], variable: "--font-cinzel", display: "swap", weight: ["500", "700"] });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: "WoW Forever Armory · Competitive Analytics", template: "%s · Forever Armory" },
  description:
    "Estadísticas competitivas de World of Warcraft: Forever construidas a partir de combat logs. Proyecto de la comunidad, no afiliado a Blizzard Entertainment.",
  applicationName: "WoW Forever Armory",
  authors: [{ name: "Luciano Colalunga" }],
  robots: { index: true, follow: true },
};

export const viewport: Viewport = { themeColor: "#0b0a0f", colorScheme: "dark" };

export default async function RootLayout({ children }: { children: ReactNode }) {
  const dataset = await getDataset();
  return (
    <html lang="es" className={`${cinzel.variable} ${inter.variable}`}>
      <body className="min-h-screen font-sans antialiased">
        <a href="#contenido" className="skip-link rounded-md bg-gold px-3 py-2 text-bg">
          Saltar al contenido
        </a>
        <SiteHeader dataset={dataset} />
        <main id="contenido" className="mx-auto max-w-7xl px-4 py-6">
          {children}
        </main>
        <footer className="mt-12 border-t border-line">
          <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-6 text-xs text-faint sm:flex-row sm:justify-between">
            <p className="max-w-2xl">
              Proyecto independiente de la comunidad, <strong>no afiliado ni avalado por Blizzard Entertainment</strong>.
              World of Warcraft y Warcraft son marcas de Blizzard Entertainment, Inc. Ningún valor de este sitio es un
              rating oficial.
            </p>
            <nav aria-label="Información" className="flex flex-wrap gap-4">
              <Link href="/methodology" className="hover:text-ink">
                Metodología
              </Link>
              <Link href="/sources" className="hover:text-ink">
                Fuentes de datos
              </Link>
              {/* La documentación OpenAPI la sirve la API (no es una página de Next): navegación completa a propósito. */}
              {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
              <a href="/api/docs" className="hover:text-ink">
                API (OpenAPI)
              </a>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
