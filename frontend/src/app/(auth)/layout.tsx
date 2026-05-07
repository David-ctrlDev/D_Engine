"use client";

/**
 * Layout for unauthenticated routes. Fits a 768 px+ viewport without
 * scrolling: the page is height-capped to ``h-screen`` and any overflow
 * is hidden. The hero panel is internally compact; the form column
 * centres in its own area and may scroll internally on extreme heights.
 */

import Link from "next/link";

import { AuthHero } from "@/components/auth-hero";
import { LocaleToggle } from "@/components/locale-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { useT } from "@/lib/i18n/provider";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const t = useT();
  return (
    <div className="grid h-screen overflow-hidden lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <AuthHero />

      <div className="relative flex h-full flex-col bg-background">
        <header className="flex shrink-0 items-center justify-between gap-2 px-6 py-4 lg:justify-end">
          <Link href="/" className="text-base font-semibold tracking-tight lg:hidden">
            {t("brand.name")}
          </Link>
          <div className="flex items-center gap-1">
            <LocaleToggle />
            <ThemeToggle />
          </div>
        </header>

        <main className="flex flex-1 items-center justify-center overflow-y-auto px-6 sm:px-10">
          <div className="w-full max-w-sm animate-in fade-in slide-in-from-bottom-2 py-6 duration-500 ease-out">
            {children}
          </div>
        </main>

        <footer className="text-muted-foreground shrink-0 px-6 pb-4 text-center text-xs lg:text-right">
          {t("auth.layout.footer")}
        </footer>
      </div>
    </div>
  );
}
