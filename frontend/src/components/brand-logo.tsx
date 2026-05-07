/**
 * dataprep brand mark — a network diagram of "two inputs → three
 * processing nodes → bar-chart output", which mirrors the product story
 * (sources → profiling → ML/LLM-ready artefacts).
 *
 * Inlined as JSX so it inherits ``currentColor`` if needed and avoids
 * an extra HTTP request. Source of truth: ``public/logo.svg``.
 */

export function BrandLogo({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 80 64"
      fill="none"
      className={className}
      role="img"
      aria-label="dataprep"
    >
      {/* Connector lines */}
      <line x1="12" y1="20" x2="40" y2="14" stroke="#c4b5fd" strokeWidth="1.2" opacity="0.5" />
      <line x1="12" y1="20" x2="40" y2="32" stroke="#c4b5fd" strokeWidth="1.2" opacity="0.5" />
      <line x1="12" y1="44" x2="40" y2="32" stroke="#c4b5fd" strokeWidth="1.2" opacity="0.5" />
      <line x1="12" y1="44" x2="40" y2="50" stroke="#c4b5fd" strokeWidth="1.2" opacity="0.5" />
      <line x1="40" y1="14" x2="68" y2="32" stroke="#c4b5fd" strokeWidth="1.2" opacity="0.5" />
      <line x1="40" y1="32" x2="68" y2="32" stroke="#c4b5fd" strokeWidth="1.2" opacity="0.5" />
      <line x1="40" y1="50" x2="68" y2="32" stroke="#c4b5fd" strokeWidth="1.2" opacity="0.5" />
      {/* Source nodes (left) */}
      <rect x="6" y="16" width="10" height="10" rx="2" fill="#7dd3fc" />
      <rect x="6" y="40" width="10" height="10" rx="2" fill="#7dd3fc" />
      {/* Processing nodes (middle) */}
      <circle cx="40" cy="14" r="4" fill="#c4b5fd" />
      <circle cx="40" cy="32" r="4" fill="#c4b5fd" />
      <circle cx="40" cy="50" r="4" fill="#c4b5fd" />
      {/* Output (right): bar-chart artefact */}
      <rect x="62" y="22" width="14" height="20" rx="3" fill="#f0a8ff" />
      <rect x="65" y="34" width="2" height="5" fill="#0a0a0c" opacity="0.4" />
      <rect x="68.5" y="30" width="2" height="9" fill="#0a0a0c" opacity="0.4" />
      <rect x="72" y="26" width="2" height="13" fill="#0a0a0c" opacity="0.4" />
    </svg>
  );
}
