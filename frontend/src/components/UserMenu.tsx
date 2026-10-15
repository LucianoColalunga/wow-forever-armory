"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { clientGet, clientSend } from "@/lib/client-api";
import type { User } from "@/lib/types";

export function UserMenu() {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    if (!document.cookie.includes("wfa_csrf=")) {
      setUser(null);
      return;
    }
    clientGet<User>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  async function logout() {
    try {
      await clientSend("POST", "/auth/logout");
    } finally {
      window.location.href = "/";
    }
  }

  if (user === undefined) return <span className="h-8 w-20 animate-pulse rounded-md bg-surface-2" aria-hidden />;
  if (user === null)
    return (
      <Link href="/login" className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-ink">
        Ingresar
      </Link>
    );
  return (
    <div className="flex items-center gap-2 text-sm">
      {user.role === "admin" && (
        <Link href="/admin" className="rounded-md bg-gold/15 px-3 py-1.5 text-gold-strong hover:bg-gold/25">
          Admin
        </Link>
      )}
      <span className="hidden text-muted lg:inline" title={user.email}>
        {user.display_name}
      </span>
      <button type="button" onClick={logout} className="rounded-md px-2 py-1.5 text-muted hover:text-ink">
        Salir
      </button>
    </div>
  );
}
