"use client";

/**
 * Auth layout — enterprise rewrite.
 *
 * Reference frame: Fivetran / dbt Cloud / Databricks / Snowflake
 * sign-in surfaces. Sober palette (warm-near-black canvas, no
 * violet saturation), 50/50 split with a hairline separator,
 * footer with legal links, status badge linked to a public
 * status page.
 *
 * Composition:
 *   • Top bar: brand mark left, Status pill + locale right.
 *   • Main: two columns split exactly 50/50 on lg+. Left is the
 *     auth surface (form + compliance row). Right is the value
 *     panel (sources + testimonial + feature row).
 *   • A 1-px hairline separator with a gradient fade lives in
 *     the gap between the two columns.
 *   • Below lg the right panel collapses into a stacked section
 *     under the form.
 *   • Footer: copyright + legal links (Terms / Privacy / Security
 *     / Status).
 *
 * Accessibility:
 *   • Single ``<h1>`` lives inside the form page (set by
 *     ``AuthPageHeader``). The right panel's headline is a
 *     ``<h2>`` so the document outline stays valid.
 *   • Vertical separator is decorative ``aria-hidden``.
 *   • Focus order: header → form (top to bottom) → footer.
 *   • Footer status link is keyboard-reachable and clearly
 *     labelled (it opens the status page in a new tab).
 */

import Link from "next/link";

import { ComplianceBadges } from "@/components/auth/compliance-badges";
import { RightPanel } from "@/components/auth/right-panel";
import { StatusBadge } from "@/components/auth/status-badge";
import { BrandLogo } from "@/components/brand-logo";
import { LocaleToggle } from "@/components/locale-toggle";
import { useT } from "@/lib/i18n/provider";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const t = useT();
  return (
    <div
      // Force-dark surface. The auth page is a marketing-grade
      // landing — we don't follow the user's theme here.
      className="dark relative flex min-h-screen flex-col text-zinc-100"
      style={{ backgroundColor: "#0A0A0B" }}
    >
      {/* Atmosphere — single very subtle indigo wash up top. No
          blobs, no animation. The page is meant to read calm. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-32 left-1/2 -z-0 size-[44rem] -translate-x-1/2 rounded-full opacity-[0.12] blur-[140px]"
        style={{
          background: "radial-gradient(circle at center, #6366F1, transparent 65%)",
        }}
      />

      {/* Top bar */}
      <header className="relative z-20 flex shrink-0 items-center justify-between border-b border-white/[0.05] px-6 py-2.5 sm:px-10">
        <Link
          href="/"
          aria-label={t("brand.name")}
          className="flex items-center gap-2 transition-opacity hover:opacity-90"
        >
          <BrandLogo className="h-6 w-auto" />
          <span className="text-[15px] font-semibold tracking-tight text-zinc-100">
            {t("brand.name")}
          </span>
        </Link>

        <div className="flex items-center gap-2.5">
          <div className="hidden sm:block">
            <StatusBadge />
          </div>
          <LocaleToggle />
        </div>
      </header>

      {/* Main — 50/50 split on lg+ */}
      <main className="relative z-10 flex flex-1 flex-col lg:flex-row">
        {/* Left — auth surface. Padding tightens at lg so the
            form fits a 1366×768 laptop without scroll. */}
        <section
          aria-labelledby="auth-page-heading"
          className="
            flex flex-1 items-center justify-center
            px-6 py-8 sm:px-10
            lg:basis-1/2 lg:px-10 lg:py-6
            xl:px-16 xl:py-10
          "
        >
          <div className="w-full max-w-[420px]">
            {/* Big brand mark above the form. Hidden on lg where
                vertical space is tight (the top nav already shows
                it); back at xl+ where there's slack. */}
            <div className="auth-field-in mb-5 hidden items-center justify-center gap-2.5 xl:mb-7 xl:flex">
              <BrandLogo className="h-9 w-auto" />
              <span className="text-[17px] font-semibold tracking-tight text-zinc-50">
                {t("brand.name")}
              </span>
            </div>

            {children}

            {/* Compliance badges — under the form. */}
            <div className="mt-5 xl:mt-7">
              <ComplianceBadges />
            </div>
          </div>
        </section>

        {/* Vertical separator — 1-px hairline with gradient fade. */}
        <div
          aria-hidden="true"
          className="hidden w-px lg:block"
          style={{
            background:
              "linear-gradient(180deg, transparent 0%, rgba(255,255,255,0.07) 18%, rgba(255,255,255,0.07) 82%, transparent 100%)",
          }}
        />

        {/* Right — value panel. Padding tightens at lg too. */}
        <section
          aria-label="Product highlights"
          className="
            border-t border-white/[0.05]
            px-6 py-8 sm:px-10
            lg:basis-1/2 lg:border-t-0 lg:px-10 lg:py-6
            xl:px-16 xl:py-10
            flex items-center
          "
        >
          <div className="w-full max-w-[480px]">
            <RightPanel />
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="relative z-20 border-t border-white/[0.05] px-6 py-2.5 sm:px-10">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 text-[11px] text-zinc-500">
          <p className="text-zinc-500">{t("auth.layout.copyright")}</p>
          <nav className="flex flex-wrap items-center gap-4" aria-label="Legal">
            <Link href="#" className="transition-colors hover:text-zinc-300">
              {t("auth.layout.terms")}
            </Link>
            <Link href="#" className="transition-colors hover:text-zinc-300">
              {t("auth.layout.privacy")}
            </Link>
            <Link href="#" className="transition-colors hover:text-zinc-300">
              {t("auth.layout.security_link")}
            </Link>
            <Link
              href="https://status.dataprep.io"
              target="_blank"
              rel="noreferrer"
              className="transition-colors hover:text-zinc-300"
            >
              {t("auth.layout.status_page")}
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
