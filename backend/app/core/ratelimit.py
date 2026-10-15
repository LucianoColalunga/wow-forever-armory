"""Rate limiting en memoria con ventana deslizante.

Alcance: por proceso. Con varias réplicas de la API cada una aplica su propio límite
(documentado en docs/SECURITY.md); para un límite global se puede reemplazar el backend
por Redis sin cambiar las dependencias de FastAPI que lo usan.
"""

from __future__ import annotations

import hmac
import ipaddress
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def hit(self, key: str, limit: int, window_s: float) -> tuple[bool, int]:
        """Registra un intento. Devuelve (permitido, segundos hasta liberar)."""
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            cutoff = now - window_s
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= limit:
                retry = int(q[0] + window_s - now) + 1
                return False, max(retry, 1)
            q.append(now)
            if now - self._last_sweep > 300:
                self._sweep(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _sweep(self, now: float) -> None:
        self._last_sweep = now
        for key in [k for k, q in self._hits.items() if not q or q[-1] < now - 3600]:
            del self._hits[key]


limiter = SlidingWindowLimiter()


def _trusted(ip: str, networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def client_ip(request: Request) -> str:
    """IP del cliente. Sólo se confía en X-Forwarded-For si el par inmediato es un proxy de confianza.

    TRUSTED_PROXIES acepta IPs o rangos CIDR (p. ej. ``172.16.0.0/12`` para la red de Docker).
    """
    settings = get_settings()
    secret = settings.proxy_shared_secret
    if secret:
        # El proxy de Next.js (Vercel) no tiene IP fija: se identifica con un secreto compartido.
        given = request.headers.get("x-wfa-proxy-secret", "")
        forwarded_ip = request.headers.get("x-wfa-client-ip", "").strip()
        if given and forwarded_ip and hmac.compare_digest(given.encode(), secret.encode()):
            try:
                ipaddress.ip_address(forwarded_ip)
                return forwarded_ip[:64]
            except ValueError:
                pass
    peer = request.client.host if request.client else "unknown"
    networks = settings.trusted_proxy_networks
    if networks and _trusted(peer, networks):
        fwd = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        # De derecha a izquierda, descartando proxies de confianza: el primero que no lo es es el cliente.
        for ip in reversed(parts):
            if not _trusted(ip, networks):
                return ip[:64]
    return peer[:64]


def enforce(request: Request, bucket: str, limit: int, window_s: float, key_suffix: str = "") -> None:
    key = f"{bucket}:{client_ip(request)}:{key_suffix}"
    ok, retry = limiter.hit(key, limit, window_s)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Probá de nuevo en unos segundos.",
            headers={"Retry-After": str(retry)},
        )


def public_limit(request: Request) -> None:
    enforce(request, "public", get_settings().rate_limit_public_per_min, 60)


def search_limit(request: Request) -> None:
    enforce(request, "search", get_settings().rate_limit_search_per_min, 60)
