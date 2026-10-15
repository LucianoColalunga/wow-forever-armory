import { NextResponse, type NextRequest } from "next/server";

/**
 * Redirección de cortesía al login para páginas que requieren sesión.
 * La autorización real la hace la API en cada solicitud (rol admin/uploader).
 */
export function middleware(req: NextRequest) {
  const hasSession = Boolean(req.cookies.get("wfa_session")?.value);
  if (!hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(req.nextUrl.pathname)}`;
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/admin/:path*", "/import/:path*"] };
