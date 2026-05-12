"use client";

/**
 * Status pill — replaces the "LIVE" badge. Stripe / Vercel pattern:
 * a small chip linking to a public status page with a coloured dot
 * indicating overall operational health.
 *
 * The dot uses ``aria-hidden`` because the meaningful colour is
 * carried by the adjacent text ("Status · Operational"); screen
 * readers don't need the visual cue.
 */

import Link from "next/link";

import { useT } from "@/lib/i18n/provider";

export function StatusBadge() {
  const t = useT();
  return (
    <Link
      href="https://status.dataprep.io"
      target="_blank"
      rel="noreferrer"
      className="group inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/[0.02] px-2.5 py-1 transition-colors hover:border-white/15 hover:bg-white/[0.04]"
    >
      <span aria-hidden="true" className="relative flex size-1.5">
        <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/60" />
        <span className="relative size-1.5 rounded-full bg-emerald-400" />
      </span>
      <span className="font-mono text-[10px] tracking-[0.14em] text-zinc-400 uppercase group-hover:text-zinc-300">
        {t("auth.layout.status_operational")}
      </span>
    </Link>
  );
}
