import { NextResponse, type NextRequest } from "next/server";

const PROTECTED = ["/admin", "/import"];

/**
 * 1. Enlaces con `?dataset=real|demo`: guardan la preferencia en la cookie y redirigen a la URL sin
 *    el parámetro, así el encabezado (selector) y la página muestran siempre el mismo conjunto.
 * 2. Redirección de cortesía al login para páginas que requieren sesión. La autorización real la
 *    hace la API en cada solicitud (rol admin/uploader).
 */
export function middleware(req: NextRequest) {
  const dataset = req.nextUrl.searchParams.get("dataset");
  if (dataset === "real" || dataset === "demo") {
    const url = req.nextUrl.clone();
    url.searchParams.delete("dataset");
    const res = NextResponse.redirect(url);
    res.cookies.set("wfa_dataset", dataset, { path: "/", maxAge: 60 * 60 * 24 * 180, sameSite: "lax" });
    return res;
  }

  const path = req.nextUrl.pathname;
  const needsSession = PROTECTED.some((p) => path === p || path.startsWith(`${p}/`));
  if (needsSession && !req.cookies.get("wfa_session")?.value) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(path)}`;
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

// Todas las páginas salvo el proxy /api, los recursos de Next.js y archivos estáticos.
export const config = { matcher: ["/((?!api/|_next/|favicon.ico|.*\\..*).*)"] };
