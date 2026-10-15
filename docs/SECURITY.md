# Seguridad

## Autenticación y autorización

- **Roles**: `admin` (todo) y `uploader` (importar). No hay registro público: un admin crea cuentas
  (`/admin` → Usuarios) o se usa `python -m app.cli create-admin` (la contraseña se pide por consola).
- **Contraseñas**: Argon2id; mínimo 12 caracteres con mayúsculas, minúsculas y números. Al iniciar
  sesión siempre se verifica un hash (también si el usuario no existe) para no revelar cuentas por tiempo.
- **Sesiones**: token aleatorio en cookie `HttpOnly`, `SameSite=Lax`, `Secure` en producción; en la
  base sólo se guarda su SHA-256. Expiran (`SESSION_TTL_HOURS`) y se revocan al salir.
- **CSRF**: toda escritura autenticada por cookie exige la cabecera `X-CSRF-Token`, que debe
  coincidir con el token ligado a esa sesión (también guardado como hash).
- **API keys** (`Authorization: Bearer wfa_…`): sólo para uploader/admin, se muestran una vez, se
  guardan como hash y pueden revocarse.
- **Admin**: todas las rutas `/api/v1/admin/*` exigen rol admin. Cada corrección pide un motivo y
  queda en `audit_log` con actor, IP, estado anterior y nuevo.

## Importación de archivos

- Límite por `Content-Length` antes de leer el cuerpo (411/413) y corte en streaming.
- Sólo `.txt`, `.log` o `.zip` con **un** archivo de log; nunca se confía en la extensión ni en el
  `Content-Type`.
- Se rechazan firmas de ejecutables (PE, ELF, Mach-O), scripts (`#!`, PHP), HTML, PDF, OLE, RAR, 7z,
  gzip, WebAssembly y cualquier byte NUL.
- Zip: sin cifrado, sin rutas con `..` o absolutas, tamaño descomprimido y relación de compresión
  acotados, contados durante la extracción (no se confía en la cabecera) → protección contra zip bombs.
- UTF-8 obligatorio y primera línea con formato de combat log.
- Los archivos se guardan con su SHA-256 como nombre (sin datos del usuario en rutas).
- Rate limit de importación por usuario/IP.

## Inyección y XSS

- SQL: sólo ORM/consultas parametrizadas; ordenamientos y métricas por listas blancas; los
  comodines de `LIKE` se escapan.
- XSS: React escapa todo el texto (nombres de jugadores incluidos); ESLint prohíbe
  `dangerouslySetInnerHTML`. La API responde JSON con `X-Content-Type-Options: nosniff` y
  `Content-Security-Policy: default-src 'none'`. La web envía CSP, `X-Frame-Options: DENY` y
  `Referrer-Policy`.
- Redirección tras login sólo a rutas internas.

## Abuso y rate limiting

Ventana deslizante por IP: lecturas públicas, búsqueda, login (por IP + email), importación y aportes.
**Límite por proceso**: con varias réplicas de la API cada una cuenta por separado; para un límite
global, reemplazar `SlidingWindowLimiter` por Redis. La IP real se toma de `X-Forwarded-For` sólo
si el par inmediato está en `TRUSTED_PROXIES` (IPs o CIDR), recorriendo de derecha a izquierda.

## Secretos y logs

- Ningún secreto en el repositorio; `.env` está ignorado y `.env.example` sólo trae valores de
  desarrollo.
- Los logs son JSON y pasan por un filtro que redacta contraseñas, tokens, cookies, cabeceras
  `Authorization`, API keys y credenciales en URLs de base de datos. No se registran cuerpos de
  solicitudes.

## Privacidad

Reportes privados (fuera de rankings y listados), ocultamiento de personajes a pedido (auditado),
sin datos personales más allá del log, y moderación de aportes de usuarios.

## Limitaciones conocidas

- Rate limit por proceso (ver arriba).
- El proxy de Next.js reenvía cargas grandes; en plataformas serverless con límite de cuerpo (por
  ejemplo 4,5 MB en funciones de Vercel) la importación de logs grandes requiere desplegar la web
  como contenedor (ver DEPLOY.md).
- La protección de fuerza bruta es por IP + email; un atacante distribuido requiere además un WAF.
