"use client";

/**
 * Right-side panel — replaces the rotating globe.
 *
 * Composition top-to-bottom:
 *   1. Hero block: eyebrow + headline + one-line subtitle.
 *   2. Source-logos grid (2 columns × 4 rows of connector names).
 *   3. Customer testimonial card with a quantified outcome.
 *   4. Three feature cells in a row, each with a lucide icon.
 *
 * No globe, no neon, no animations. The composition reads
 * "Fivetran / dbt Cloud / Databricks" — monochrome surfaces,
 * sober accent on indigo, real signals (sources, quote,
 * measurable outcome).
 */

import { BarChart3, BrainCircuit, Plug } from "lucide-react";
import dynamic from "next/dynamic";

import { useT } from "@/lib/i18n/provider";

// Mini globe is client-only (WebGL canvas). Loaded dynamically
// so the right panel renders synchronously without it.
const MiniGlobe = dynamic(
  () => import("@/components/auth/mini-globe").then((m) => m.MiniGlobe),
  { ssr: false },
);

const SOURCES: { name: string; tone: string }[] = [
  { name: "PostgreSQL", tone: "#7dd3fc" },
  { name: "MySQL", tone: "#a5b4fc" },
  { name: "Snowflake", tone: "#7dd3fc" },
  { name: "BigQuery", tone: "#a5b4fc" },
  { name: "SQL Server", tone: "#c4b5fd" },
  { name: "Azure SQL", tone: "#a5b4fc" },
  { name: "Redshift", tone: "#c4b5fd" },
  { name: "Amazon S3", tone: "#a5b4fc" },
];

export function RightPanel() {
  const t = useT();
  return (
    <div className="space-y-4 xl:space-y-6" aria-hidden="true">
      {/* Hero block — tighter type at lg so the right column fits
          a 1366×768 viewport. */}
      <div className="space-y-2">
        <p className="font-mono text-[10.5px] tracking-[0.18em] text-indigo-300/80 uppercase">
          {t("right.eyebrow")}
        </p>
        <h2 className="text-[1.35rem] leading-[1.15] font-semibold tracking-[-0.02em] text-balance text-zinc-50 xl:text-[1.7rem]">
          {t("right.headline")}
        </h2>
        <p className="hidden max-w-[400px] text-[13px] leading-relaxed text-zinc-400 xl:block">
          {t("right.sub")}
        </p>
      </div>

      {/* Source connectors grid */}
      <div className="grid grid-cols-2 gap-2">
        {SOURCES.map((s) => (
          <div
            key={s.name}
            className="flex items-center gap-2 rounded-md border border-white/[0.06] bg-white/[0.018] px-3 py-2 text-[12px] font-medium tracking-tight text-zinc-300 transition-colors hover:border-white/[0.12] hover:bg-white/[0.035]"
          >
            <span
              className="size-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: s.tone, opacity: 0.7 }}
            />
            {s.name}
          </div>
        ))}
      </div>

      {/* Testimonial — compact at lg. */}
      <blockquote className="rounded-lg border border-white/[0.08] bg-white/[0.02] p-3.5 xl:p-5">
        <p className="text-[13px] leading-relaxed text-zinc-100 xl:text-[14.5px]">
          “{t("right.testimonial_quote")}”
        </p>
        <footer className="mt-2.5 flex items-center gap-2.5">
          <div
            aria-hidden="true"
            className="flex size-6 items-center justify-center rounded-full text-[10px] font-semibold text-zinc-900 xl:size-7 xl:text-[11px]"
            style={{ background: "linear-gradient(135deg, #a5b4fc, #c4b5fd)" }}
          >
            MG
          </div>
          <div className="min-w-0">
            <p className="text-[11.5px] font-medium text-zinc-200 xl:text-[12px]">
              {t("right.testimonial_author")}
            </p>
            <p className="text-[10px] text-zinc-500 xl:text-[10.5px]">
              {t("right.testimonial_role")}
            </p>
          </div>
        </footer>
      </blockquote>

      {/* Feature row — compact at lg. */}
      <div className="grid grid-cols-3 gap-3 border-t border-white/[0.06] pt-3.5 xl:pt-5">
        <FeatureCell
          icon={<Plug className="size-4 text-indigo-300" strokeWidth={2} />}
          title={t("right.feature_one")}
          sub={t("right.feature_one_sub")}
        />
        <FeatureCell
          icon={<BrainCircuit className="size-4 text-indigo-300" strokeWidth={2} />}
          title={t("right.feature_two")}
          sub={t("right.feature_two_sub")}
        />
        <FeatureCell
          icon={<BarChart3 className="size-4 text-indigo-300" strokeWidth={2} />}
          title={t("right.feature_three")}
          sub={t("right.feature_three_sub")}
        />
      </div>

      {/* Global infrastructure band — small rotating globe + stat. */}
      <div className="flex items-center gap-3 border-t border-white/[0.06] pt-3.5 xl:gap-4 xl:pt-5">
        <div className="size-[72px] shrink-0 overflow-hidden rounded-full ring-1 ring-white/[0.08] xl:size-[88px]">
          <MiniGlobe />
        </div>
        <div className="min-w-0 space-y-0.5 xl:space-y-1">
          <p className="font-mono text-[10px] tracking-[0.18em] text-zinc-500 uppercase">
            {t("right.infra_eyebrow")}
          </p>
          <p className="text-[12px] font-medium tracking-tight text-zinc-100 xl:text-[12.5px]">
            {t("right.infra_metric")}
          </p>
          <p className="hidden text-[10.5px] leading-snug text-zinc-500 xl:block">
            {t("right.infra_sub")}
          </p>
        </div>
      </div>
    </div>
  );
}

function FeatureCell({
  icon,
  title,
  sub,
}: {
  icon: React.ReactNode;
  title: string;
  sub: string;
}) {
  return (
    <div className="space-y-1.5">
      {icon}
      <p className="text-[11.5px] leading-tight font-medium tracking-tight text-zinc-100">
        {title}
      </p>
      <p className="text-[10.5px] leading-snug text-zinc-500">{sub}</p>
    </div>
  );
}
