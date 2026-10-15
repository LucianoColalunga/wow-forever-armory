import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // Next.js necesita estilos/scripts inline para hidratar; no se cargan scripts de terceros.
      "script-src 'self' 'unsafe-inline'" + (process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : ""),
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data:",
      "font-src 'self' data:",
      "connect-src 'self'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
];

// Dominio principal en producción (p. ej. wowforeverarmory.com.ar). Si está definido, en el deploy de
// producción de Vercel cualquier otro host (como <proyecto>.vercel.app) redirige a este.
const canonicalHost = process.env.CANONICAL_HOST?.trim().toLowerCase();

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    // /api/* es el proxy: conserva las cabeceras de seguridad que define la API (incluida la CSP de /api/docs).
    return [{ source: "/((?!api/).*)", headers: securityHeaders }];
  },
  async redirects() {
    // www.<dominio> → <dominio> (una sola URL canónica).
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "www\\.(?<domain>.+)" }],
        destination: "https://:domain/:path*",
        permanent: true,
      },
      ...(canonicalHost && process.env.VERCEL_ENV === "production"
        ? [
            {
              source: "/:path*",
              missing: [{ type: "host" as const, value: canonicalHost.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") }],
              destination: `https://${canonicalHost}/:path*`,
              permanent: true,
            },
          ]
        : []),
    ];
  },
};

export default nextConfig;
