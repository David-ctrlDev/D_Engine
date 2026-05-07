"use client";

/**
 * Marketing-side panel rendered next to the auth forms on desktop.
 *
 * Composition (back to front):
 *   1. Drifting radial blobs (sky / indigo / fuchsia)
 *   2. Static dot-grid texture
 *   3. SVG pipeline visualization with flowing data tokens
 *   4. Headline + bento feature cards
 *
 * All motion respects ``prefers-reduced-motion``. All copy is i18n-aware
 * via the LocaleProvider — switching locale here updates instantly.
 */

import { Boxes, Brain, Database, Sparkles, Wand2 } from "lucide-react";

import { BrandLogo } from "@/components/brand-logo";
import type { DictionaryKey } from "@/lib/i18n/dictionaries";
import { useT } from "@/lib/i18n/provider";

const FEATURES: { icon: typeof Database; titleKey: DictionaryKey; bodyKey: DictionaryKey }[] = [
  {
    icon: Database,
    titleKey: "hero.feature.any_source.title",
    bodyKey: "hero.feature.any_source.body",
  },
  { icon: Wand2, titleKey: "hero.feature.profiled.title", bodyKey: "hero.feature.profiled.body" },
  { icon: Boxes, titleKey: "hero.feature.versioned.title", bodyKey: "hero.feature.versioned.body" },
  { icon: Brain, titleKey: "hero.feature.ml_llm.title", bodyKey: "hero.feature.ml_llm.body" },
];

export function AuthHero() {
  const t = useT();

  return (
    <section
      aria-hidden="true"
      className="relative hidden h-screen overflow-hidden bg-zinc-950 text-zinc-100 lg:flex lg:flex-col lg:justify-between lg:gap-3 lg:p-6 xl:gap-6 xl:p-10 [@media(max-height:760px)]:lg:gap-2 [@media(max-height:760px)]:lg:p-5"
    >
      {/* ── Layer 1: drifting blobs ──────────────────────────────── */}
      <div className="absolute inset-0 -z-10">
        <div
          className="blob-a absolute -left-32 -top-32 h-[28rem] w-[28rem] rounded-full opacity-50 blur-3xl"
          style={{
            background: "radial-gradient(circle at 30% 30%, oklch(0.62 0.24 264), transparent 65%)",
          }}
        />
        <div
          className="blob-b absolute -right-32 top-1/3 h-[26rem] w-[26rem] rounded-full opacity-40 blur-3xl"
          style={{
            background: "radial-gradient(circle at 50% 50%, oklch(0.72 0.2 200), transparent 60%)",
          }}
        />
        <div
          className="blob-c absolute -bottom-32 left-1/3 h-[24rem] w-[24rem] rounded-full opacity-30 blur-3xl"
          style={{
            background: "radial-gradient(circle at 50% 50%, oklch(0.68 0.22 320), transparent 65%)",
          }}
        />
        {/* Layer 2: dot grid */}
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage: "radial-gradient(currentColor 1px, transparent 1px)",
            backgroundSize: "22px 22px",
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-transparent to-zinc-950/60" />
      </div>

      <div className="flex items-center justify-between">
        <BrandMark />
        <StatusPill label={t("hero.status_pill")} />
      </div>

      {/* Middle block — headline DOMINANT, then supporting evidence.
       * Spacing tightens at small viewport heights so notebooks
       * (≤ 760px) still fit headline + bento + pipeline without
       * clipping. The pipeline itself is hidden below 720px because
       * the SVG is the easiest piece to drop without sacrificing
       * the value proposition. */}
      <div className="space-y-4 [@media(max-height:760px)]:space-y-3">
        <div className="space-y-2.5 [@media(max-height:760px)]:space-y-2">
          <p className="text-[11px] uppercase tracking-[0.2em] text-zinc-400">
            {t("hero.eyebrow")}
          </p>
          <h1 className="text-[1.75rem] font-semibold leading-[1.05] tracking-tight lg:text-[2rem] xl:text-[2.75rem] [@media(max-height:760px)]:lg:text-[1.6rem]">
            {t("hero.headline_a")}
            <br />
            <span className="bg-gradient-to-r from-sky-300 via-indigo-300 to-fuchsia-300 bg-clip-text text-transparent">
              {t("hero.headline_b")}
            </span>
            <span className="text-zinc-100">{t("hero.headline_c")}</span>
          </h1>
          <p className="max-w-md text-sm leading-relaxed text-zinc-400 [@media(max-height:760px)]:text-[13px]">
            {t("hero.subtitle")}
          </p>
        </div>

        {/* Bento next — supporting evidence for the headline claim. */}
        <div className="grid grid-cols-2 gap-2.5 [@media(max-height:760px)]:gap-2">
          {FEATURES.map(({ icon: Icon, titleKey, bodyKey }) => (
            <div
              key={titleKey}
              className="group rounded-lg border border-white/5 bg-white/[0.02] px-3.5 py-3 transition-colors duration-200 hover:border-white/10 hover:bg-white/[0.04] [@media(max-height:760px)]:px-3 [@media(max-height:760px)]:py-2.5"
            >
              <div className="mb-2 inline-flex size-7 items-center justify-center rounded bg-white/5 ring-1 ring-white/10 [@media(max-height:760px)]:mb-1.5 [@media(max-height:760px)]:size-6">
                <Icon className="size-3.5" />
              </div>
              <p className="text-sm font-medium leading-tight">{t(titleKey)}</p>
              <p className="mt-1 text-xs leading-snug text-zinc-400">{t(bodyKey)}</p>
            </div>
          ))}
        </div>

        {/* Pipeline last — "and here's how it flows together". Hidden
         * on short viewports (notebooks, ≤ 720px) because the SVG +
         * label row is the most droppable piece; the bento above
         * already carries the message. */}
        <div className="[@media(max-height:720px)]:hidden">
          <Pipeline
            sampleRunLabel={t("hero.sample_run")}
            stages={[
              { label: t("hero.node.source"), sub: "postgres" },
              { label: t("hero.node.profile"), sub: "rules" },
              { label: t("hero.node.train"), sub: "model" },
              { label: t("hero.node.serve"), sub: "agents", highlight: true },
            ]}
          />
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs text-zinc-400">
        <Sparkles className="size-3" />
        {t("brand.version_note")}
      </div>
    </section>
  );
}

function BrandMark() {
  return (
    <div className="flex items-center gap-2.5">
      <BrandLogo className="h-7 w-auto" />
      <span className="text-base font-semibold tracking-tight">dataprep</span>
    </div>
  );
}

function StatusPill({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-zinc-300">
      <span className="relative flex size-2">
        <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/70" />
        <span className="relative size-2 rounded-full bg-emerald-400" />
      </span>
      {label}
    </div>
  );
}

/* ─── Pipeline ───────────────────────────────────────────────────────────
 * Source → Profile → Train → Serve, with data tokens flowing along each
 * connector. The last stage (``Serve``) is highlighted because that's
 * where the product story lands: serving ML models and LLM agents.
 * The viewBox is wide and short so the panel doesn't grow tall. */

interface Stage {
  label: string;
  sub: string;
  highlight?: boolean;
}

function Pipeline({
  sampleRunLabel,
  stages,
}: {
  sampleRunLabel: string;
  stages: [Stage, Stage, Stage, Stage];
}) {
  // Horizontal positions for 4 evenly-spaced 50-px-wide nodes.
  const nodeW = 50;
  const xs = [10, 110, 210, 310];

  return (
    <div className="rounded-xl border border-white/5 bg-gradient-to-b from-white/[0.04] to-transparent px-4 py-3">
      <div className="mb-2 flex items-center gap-2 text-[9px] uppercase tracking-widest text-zinc-500">
        <span className="size-1 rounded-full bg-zinc-500" />
        {sampleRunLabel}
      </div>
      <svg viewBox="0 0 380 70" className="w-full" fill="none" xmlns="http://www.w3.org/2000/svg">
        {stages.map((stage, i) => (
          <PipelineNode key={i} x={xs[i]} width={nodeW} {...stage} />
        ))}
        {/* 3 connectors between the 4 nodes */}
        {[0, 1, 2].map((i) => {
          const x1 = xs[i] + nodeW;
          const x2 = xs[i + 1];
          const path = `M ${x1} 35 C ${(x1 + x2) / 2} 35, ${(x1 + x2) / 2} 35, ${x2} 35`;
          return (
            <g key={`pipe-${i}`}>
              <path d={path} stroke="oklch(0.55 0.05 264)" strokeOpacity="0.4" strokeWidth="1.5" />
              {[0, 1.6, 3.2].map((delay) => (
                <circle key={`t-${i}-${delay}`} r="2.5" fill={i === 2 ? "#F0ABFC" : "#A5B4FC"}>
                  <animateMotion
                    dur="4.5s"
                    repeatCount="indefinite"
                    begin={`${delay}s`}
                    path={path}
                  />
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function PipelineNode({
  x,
  width,
  label,
  sub,
  highlight = false,
}: {
  x: number;
  width: number;
  label: string;
  sub: string;
  highlight?: boolean;
}) {
  const id = `pipeNode-${x}`;
  return (
    <g>
      <rect
        x={x}
        y={15}
        width={width}
        height={40}
        rx={8}
        fill={highlight ? `url(#${id})` : "oklch(0.22 0.005 264)"}
        stroke={highlight ? "oklch(0.7 0.18 264)" : "oklch(0.32 0.01 264)"}
        strokeWidth={1}
      />
      <text
        x={x + width / 2}
        y={32}
        textAnchor="middle"
        fontSize="9"
        fontWeight="600"
        fill={highlight ? "#0c0a09" : "#e4e4e7"}
      >
        {label}
      </text>
      <text
        x={x + width / 2}
        y={45}
        textAnchor="middle"
        fontSize="7"
        fill={highlight ? "#1c1917" : "#a1a1aa"}
        fontFamily="ui-monospace, Menlo, monospace"
      >
        {sub}
      </text>
      <defs>
        <linearGradient
          id={id}
          x1={x}
          y1={15}
          x2={x + width}
          y2={55}
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#A5B4FC" />
          <stop offset="1" stopColor="#F0ABFC" />
        </linearGradient>
      </defs>
    </g>
  );
}
