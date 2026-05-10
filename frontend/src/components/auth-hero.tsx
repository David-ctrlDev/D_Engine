"use client";

/**
 * Editorial-warm auth hero.
 *
 * Direction: warm near-black (no cool zinc) + a single saffron accent +
 * a serif display headline. No drifting blobs, no animated SVG, no
 * bento grid — the previous take leaned too "generic SaaS dark".
 *
 * Layout, top to bottom:
 *   1. Brand mark + status ribbon
 *   2. A small "issue / volume" line (mock magazine masthead)
 *   3. Editorial headline — sans-italic-serif mix, large
 *   4. Pull quote / subtitle
 *   5. A static, hand-drawn-ish data flow strip (raw rows → clean table)
 *   6. Three numbered footnotes
 *   7. Footer
 *
 * Every accent is the same saffron — restraint is the point. The logo
 * keeps its own (sky / lavender / fuchsia) palette as a deliberate
 * counterpoint to the warm background.
 */

import { ArrowRight } from "lucide-react";

import { BrandLogo } from "@/components/brand-logo";
import type { DictionaryKey } from "@/lib/i18n/dictionaries";
import { useT } from "@/lib/i18n/provider";

// Saffron, used everywhere an accent is needed. Defined once so a
// future re-skin only edits this constant.
const ACCENT = "#f5a524";

const FOOTNOTES: { numKey: DictionaryKey; titleKey: DictionaryKey; bodyKey: DictionaryKey }[] = [
  {
    numKey: "hero.note.one.num",
    titleKey: "hero.note.one.title",
    bodyKey: "hero.note.one.body",
  },
  {
    numKey: "hero.note.two.num",
    titleKey: "hero.note.two.title",
    bodyKey: "hero.note.two.body",
  },
  {
    numKey: "hero.note.three.num",
    titleKey: "hero.note.three.title",
    bodyKey: "hero.note.three.body",
  },
];

export function AuthHero() {
  const t = useT();

  return (
    <section
      aria-hidden="true"
      // The warm near-black `#0d0a08` reads less synthetic than zinc-950
      // in side-by-side tests; the noise filter sells it as "paper, not
      // pixels" without needing a real texture image.
      className="relative hidden h-screen overflow-hidden text-stone-100 lg:flex lg:flex-col lg:justify-between lg:gap-4 lg:p-8 xl:gap-6 xl:p-10 [@media(max-height:760px)]:lg:gap-3 [@media(max-height:760px)]:lg:p-6"
      style={{ backgroundColor: "#0d0a08" }}
    >
      {/* Background — a single off-centre warm wash, plus a hairline
          rule at the right edge. Static. No motion. */}
      <div className="absolute inset-0 -z-10">
        <div
          className="absolute -left-1/4 top-1/3 size-[42rem] rounded-full opacity-[0.18] blur-3xl"
          style={{
            background: `radial-gradient(circle at center, ${ACCENT}, transparent 60%)`,
          }}
        />
        {/* Subtle film-grain via SVG turbulence — adds organic texture
            without a binary asset. Opacity is held very low (~0.04). */}
        <svg
          className="absolute inset-0 h-full w-full opacity-[0.045] mix-blend-overlay"
          xmlns="http://www.w3.org/2000/svg"
        >
          <filter id="hero-grain">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch" />
            <feColorMatrix values="0 0 0 0 1   0 0 0 0 1   0 0 0 0 1   0 0 0 0.6 0" />
          </filter>
          <rect width="100%" height="100%" filter="url(#hero-grain)" />
        </svg>
        {/* Right-edge rule, kissing the form column. */}
        <div className="absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-stone-100/10 to-transparent" />
      </div>

      {/* Top — masthead row */}
      <header className="flex items-center justify-between">
        <BrandMark />
        <Masthead label={t("hero.masthead")} />
      </header>

      {/* Middle — editorial display */}
      <div className="space-y-6 [@media(max-height:760px)]:space-y-4">
        <p
          className="text-[10px] uppercase tracking-[0.32em] text-stone-400"
          style={{ fontFamily: "var(--font-fraunces), Georgia, serif" }}
        >
          {t("hero.eyebrow")}
        </p>

        {/*
         * Headline. Two lines, the second is italic Fraunces — that
         * tiny shift of voice from the first line carries most of
         * the editorial weight. The accent word gets a saffron
         * underline drawn with a CSS pseudo so we don't need an SVG.
         */}
        <h1
          className="font-serif text-[2.25rem] font-medium leading-[1.04] tracking-[-0.01em] text-stone-100 xl:text-[3.25rem] [@media(max-height:760px)]:lg:text-[1.85rem]"
          style={{ fontFamily: "var(--font-fraunces), Georgia, serif" }}
        >
          {t("hero.headline_a")}
          <br />
          <span className="font-normal italic text-stone-300">
            {t("hero.headline_b")}{" "}
            <span
              className="relative whitespace-nowrap"
              style={{ color: ACCENT }}
            >
              {t("hero.headline_c")}
              {/* hand-drawn underline — slight pen-skip */}
              <svg
                aria-hidden="true"
                viewBox="0 0 200 12"
                className="pointer-events-none absolute -bottom-1 left-0 h-2 w-full"
                preserveAspectRatio="none"
              >
                <path
                  d="M2 7 C 50 2, 100 11, 198 5"
                  stroke={ACCENT}
                  strokeWidth="2"
                  strokeLinecap="round"
                  fill="none"
                  opacity="0.85"
                />
              </svg>
            </span>
          </span>
        </h1>

        {/* Subtitle — set in sans, narrow column, neutral. */}
        <p className="max-w-md text-[15px] leading-relaxed text-stone-400 [@media(max-height:760px)]:text-[13px]">
          {t("hero.subtitle")}
        </p>

        {/* Static "before / after" strip — raw CSV bytes on the left,
            tidied table on the right, with a soft saffron arrow. No
            animation; the contrast carries the meaning. */}
        <FlowStrip
          beforeLabel={t("hero.flow.before")}
          afterLabel={t("hero.flow.after")}
        />
      </div>

      {/* Bottom — three numbered footnotes laid out like a book's spine */}
      <div className="grid grid-cols-3 gap-5 border-t border-stone-100/[0.06] pt-5 [@media(max-height:760px)]:gap-3 [@media(max-height:760px)]:pt-3">
        {FOOTNOTES.map(({ numKey, titleKey, bodyKey }) => (
          <div key={numKey} className="space-y-1.5">
            <div
              className="text-[11px] tracking-widest"
              style={{ color: ACCENT, fontFamily: "var(--font-fraunces), Georgia, serif" }}
            >
              {t(numKey)}
            </div>
            <div className="text-[13px] font-medium leading-tight text-stone-200 [@media(max-height:760px)]:text-[12px]">
              {t(titleKey)}
            </div>
            <p className="text-[11px] leading-snug text-stone-500">{t(bodyKey)}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ─── Pieces ────────────────────────────────────────────────────────── */

function BrandMark() {
  return (
    <div className="flex items-center gap-2.5">
      <BrandLogo className="h-7 w-auto" />
      <span className="text-base font-semibold tracking-tight">dataprep</span>
    </div>
  );
}

function Masthead({ label }: { label: string }) {
  return (
    <div
      className="flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] text-stone-400"
      style={{ fontFamily: "var(--font-fraunces), Georgia, serif" }}
    >
      <span className="h-px w-4" style={{ backgroundColor: ACCENT }} />
      {label}
    </div>
  );
}

/**
 * Hand-set "before / after" strip:
 *
 *   ┌─────────────────┐    →    ┌─────────────────┐
 *   │ raw,ish,csv     │         │ Customers       │
 *   │ "1,Jane,,US"    │         │ ────────────    │
 *   │ "2,??,42,??"    │         │ id  name age... │
 *   └─────────────────┘         └─────────────────┘
 *
 * The arrow between is the sole instance of saffron on this surface
 * besides the headline accent and the masthead rule.
 */
function FlowStrip({ beforeLabel, afterLabel }: { beforeLabel: string; afterLabel: string }) {
  return (
    <div className="flex items-stretch gap-3 [@media(max-height:760px)]:gap-2">
      {/* BEFORE — raw bytes */}
      <div className="flex min-w-0 flex-1 flex-col gap-2 rounded-md border border-stone-100/[0.06] bg-stone-100/[0.015] p-3 [@media(max-height:760px)]:p-2.5">
        <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-[0.22em] text-stone-500">
          <span className="size-1 rounded-full bg-stone-500" />
          {beforeLabel}
        </div>
        <pre className="overflow-hidden text-[10px] leading-[1.5] text-stone-400 [@media(max-height:760px)]:text-[9px]">
          <code>{`id,name,age,country
1,Jane,,US
2,?,42,??
3,Lee,29,SG
4,, ,US`}</code>
        </pre>
      </div>

      {/* Arrow — single saffron tick */}
      <div className="flex shrink-0 items-center" aria-hidden="true">
        <ArrowRight className="size-4" style={{ color: ACCENT }} strokeWidth={2.5} />
      </div>

      {/* AFTER — tidied table */}
      <div className="flex min-w-0 flex-1 flex-col gap-2 rounded-md border border-stone-100/[0.08] bg-stone-100/[0.025] p-3 [@media(max-height:760px)]:p-2.5">
        <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-[0.22em] text-stone-400">
          <span className="size-1 rounded-full" style={{ backgroundColor: ACCENT }} />
          {afterLabel}
        </div>
        <table className="w-full text-[10px] leading-[1.5] text-stone-200 [@media(max-height:760px)]:text-[9px]">
          <thead className="text-stone-500">
            <tr className="border-b border-stone-100/10">
              <th className="text-left font-medium">id</th>
              <th className="text-left font-medium">name</th>
              <th className="text-left font-medium">age</th>
              <th className="text-left font-medium">country</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            <tr>
              <td>1</td>
              <td>Jane</td>
              <td className="text-stone-500">—</td>
              <td>US</td>
            </tr>
            <tr>
              <td>2</td>
              <td className="text-stone-500">—</td>
              <td>42</td>
              <td className="text-stone-500">—</td>
            </tr>
            <tr>
              <td>3</td>
              <td>Lee</td>
              <td>29</td>
              <td>SG</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
