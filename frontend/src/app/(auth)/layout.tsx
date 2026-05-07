/**
 * Layout for unauthenticated pages — login, register, verification.
 *
 * Centres the page content in a card, branding top-left, theme toggle
 * top-right. Public: doesn't gate on auth state.
 */

import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background flex min-h-screen flex-col">
      <header className="flex items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          dataprep
        </Link>
        <ThemeToggle />
      </header>
      <main className="flex flex-1 items-center justify-center px-6 py-10">
        <div className="w-full max-w-md">{children}</div>
      </main>
      <footer className="text-muted-foreground px-6 py-4 text-center text-xs">
        v0 — multi-tenant data preparation platform
      </footer>
    </div>
  );
}
