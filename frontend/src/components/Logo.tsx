/**
 * Espada rúnica helada, inspirada en la estética de Rasganorte (WotLK).
 * Diseño original dibujado a mano (no usa logos ni arte de Blizzard ni de terceros).
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
        <linearGradient id="wfa-blade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#5fb6ea" />
          <stop offset="0.5" stopColor="#f2fbff" />
          <stop offset="1" stopColor="#3d86c6" />
        </linearGradient>
        <linearGradient id="wfa-steel" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#c9d6e3" />
          <stop offset="1" stopColor="#5b6b80" />
        </linearGradient>
        <radialGradient id="wfa-glow" cx="0.5" cy="0.55" r="0.5">
          <stop offset="0" stopColor="#7fd3ff" stopOpacity="0.4" />
          <stop offset="1" stopColor="#7fd3ff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="32" cy="32" r="30" fill="#0b1220" />
      <circle cx="32" cy="34" r="26" fill="url(#wfa-glow)" />
      <circle cx="32" cy="32" r="28" fill="none" stroke="url(#wfa-ring)" strokeWidth="2.5" />
      {/* Hoja dentada */}
      <path
        d="M26.5 27 L37.5 27 L36 34 L38.5 39 L35.8 45 L37 49.5 L32 60 L27 49.5 L28.2 45 L25.5 39 L28 34 Z"
        fill="url(#wfa-blade)"
        stroke="#e6f8ff"
        strokeWidth="0.7"
        strokeLinejoin="round"
      />
      <path d="M32 29 V55" stroke="#2a6fb5" strokeWidth="1" opacity="0.7" />
      {/* Runas en la hoja */}
      <path
        d="M30.3 33 L32 35 L33.7 33 M30.3 39.5 H33.7 M31 42 L33 44 M33 42 L31 44 M30.6 48 L32 50 L33.4 48"
        stroke="#ffffff"
        strokeWidth="0.9"
        strokeLinecap="round"
        fill="none"
        opacity="0.95"
      />
      {/* Guarda con cuernos */}
      <path
        d="M14 17 Q18 25 26 24 L32 28.5 L38 24 Q46 25 50 17 Q47 28 38.5 28.5 L32 31 L25.5 28.5 Q17 28 14 17 Z"
        fill="url(#wfa-steel)"
        stroke="#e6f0f8"
        strokeWidth="0.7"
        strokeLinejoin="round"
      />
      {/* Cráneo central */}
      <path d="M28.5 21 Q28.5 16.5 32 16.5 Q35.5 16.5 35.5 21 L34.3 25 L29.7 25 Z" fill="#dfe8f0" stroke="#0b1220" strokeWidth="0.5" />
      <circle cx="30.6" cy="21" r="1.1" fill="#7fe0ff" />
      <circle cx="33.4" cy="21" r="1.1" fill="#7fe0ff" />
      {/* Empuñadura y pomo */}
      <rect x="30.6" y="8" width="2.8" height="8.5" rx="0.6" fill="#3a2f4a" stroke="#9fb3c8" strokeWidth="0.5" />
      <path d="M30.6 10.5 L33.4 12 M30.6 13 L33.4 14.5" stroke="#9fb3c8" strokeWidth="0.5" />
      <path d="M32 3 L34.6 6 L32 9 L29.4 6 Z" fill="#8fd6ff" stroke="#e6f8ff" strokeWidth="0.6" />
    </svg>
  );
}
