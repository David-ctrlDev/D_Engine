"use client";

/**
 * Compliance row — the SOC 2 / ISO 27001 / GDPR / TLS pills that
 * live under the sign-in form. Replaces the previous "encrypted
 * connection · multi-tenant" line, which read as fluff against
 * actual enterprise procurement signals.
 *
 * Each pill carries a native ``title`` (tooltip) explaining what
 * the badge means. The hover state lifts the pill slightly so
 * the row feels alive without animating.
 */

import { Globe, Lock, Network, ShieldCheck } from "lucide-react";

import type { DictionaryKey } from "@/lib/i18n/dictionaries";
import { useT } from "@/lib/i18n/provider";

const BADGES: {
  icon: typeof ShieldCheck;
  textKey: DictionaryKey;
  tooltipKey: DictionaryKey;
}[] = [
  { icon: ShieldCheck, textKey: "compliance.soc2", tooltipKey: "compliance.soc2_tooltip" },
  { icon: Lock, textKey: "compliance.iso", tooltipKey: "compliance.iso_tooltip" },
  { icon: Globe, textKey: "compliance.gdpr", tooltipKey: "compliance.gdpr_tooltip" },
  { icon: Network, textKey: "compliance.tls", tooltipKey: "compliance.tls_tooltip" },
];

export function ComplianceBadges() {
  const t = useT();
  return (
    <div
      className="flex flex-wrap items-center justify-center gap-1.5"
      role="list"
      aria-label="Compliance certifications"
    >
      {BADGES.map(({ icon: Icon, textKey, tooltipKey }) => (
        <span
          key={textKey}
          role="listitem"
          title={t(tooltipKey)}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.02] px-2 py-1 text-[10.5px] font-medium tracking-tight text-zinc-400 transition-colors hover:border-white/[0.14] hover:bg-white/[0.04] hover:text-zinc-200"
        >
          <Icon className="size-3 text-zinc-500" strokeWidth={2} />
          {t(textKey)}
        </span>
      ))}
    </div>
  );
}
