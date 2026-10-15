/**
 * Sello propio de estética helada: anillo de escarcha, esquirlas de hielo y una corona rúnica.
 * Diseño original (no usa logos ni arte de Blizzard ni de terceros).
 */
export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="wfa-ring" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#d6f4ff" />
          <stop offset="0.5" stopColor="#6cc4f5" />
          <stop offset="1" stopColor="#2a6fb5" />
        </linearGradient>
        <linearGradient id="wfa-ice" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f2fbff" />
          <stop offset="0.45" stopColor="#8fd6ff" />
          <stop offset="1" stopColor="#2a6fb5" />
        </linearGradient>
        <radialGradient id="wfa-glow" cx="0.5" cy="0.45" r="0.5">
          <stop offset="0" stopColor="#7fd3ff" stopOpacity="0.35" />
          <stop offset="1" stopColor="#7fd3ff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="32" cy="32" r="30" fill="#0b1220" />
      <circle cx="32" cy="32" r="26" fill="url(#wfa-glow)" />
      <circle cx="32" cy="32" r="28" fill="none" stroke="url(#wfa-ring)" strokeWidth="2.5" />
      <circle cx="32" cy="32" r="23" fill="none" stroke="#8fd6ff" strokeWidth="0.8" strokeDasharray="2 4" opacity="0.6" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
        <path key={a} d="M32 1.5 L34 6 L32 10 L30 6 Z" fill="#cdefff" transform={`rotate(${a} 32 32)`} opacity="0.9" />
      ))}
      {/* Corona de hielo */}
      <path
        d="M16 41 L19.5 22 L25.5 31 L32 12 L38.5 31 L44.5 22 L48 41 Z"
        fill="url(#wfa-ice)"
        stroke="#e6f8ff"
        strokeWidth="0.8"
        strokeLinejoin="round"
      />
      <rect x="16" y="40" width="32" height="6" rx="1" fill="#17406f" stroke="#9fe3ff" strokeWidth="0.8" />
      {[24, 32, 40].map((x) => (
        <path key={x} d={`M${x} 41.2 L${x + 1.8} 43 L${x} 44.8 L${x - 1.8} 43 Z`} fill="#c8f3ff" />
      ))}
      {/* Runa central */}
      <path
        d="M32 21 V33 M32 26 L28.5 22.5 M32 26 L35.5 22.5 M29.5 33 H34.5"
        stroke="#ffffff"
        strokeWidth="1.3"
        strokeLinecap="round"
        fill="none"
        opacity="0.95"
      />
      {/* Carámbanos */}
      <path d="M20 46 L21.5 51 L23 46 Z M28 46 L29.2 52.5 L30.4 46 Z M35.5 46 L36.8 51.5 L38 46 Z M42 46 L43.2 50 L44.4 46 Z" fill="#9fe3ff" opacity="0.85" />
    </svg>
  );
}
