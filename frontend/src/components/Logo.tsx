/** Sello propio: anillo rúnico con llama eterna (no usa logos de Blizzard ni de terceros). */
export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="wfa-flame" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#c8643c" />
          <stop offset="0.6" stopColor="#d8b25a" />
          <stop offset="1" stopColor="#f6e2a8" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="28" fill="none" stroke="#d8b25a" strokeWidth="2" opacity="0.85" />
      <circle cx="32" cy="32" r="22" fill="none" stroke="#59c3b6" strokeWidth="1" strokeDasharray="3 5" opacity="0.7" />
      {[0, 60, 120, 180, 240, 300].map((a) => (
        <rect
          key={a}
          x="31"
          y="2.5"
          width="2"
          height="7"
          fill="#d8b25a"
          transform={`rotate(${a} 32 32)`}
          opacity="0.9"
        />
      ))}
      <path
        d="M32 14c4 7 10 11 10 20a10 10 0 0 1-20 0c0-5 3-8 5-11 1 3 2 5 4 6-1-5 0-10 1-15z"
        fill="url(#wfa-flame)"
      />
      <path d="M32 30c2 3 4 5 4 8a4 4 0 0 1-8 0c0-2 2-4 4-8z" fill="#0b0a0f" opacity="0.55" />
    </svg>
  );
}
