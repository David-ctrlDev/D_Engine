"use client";

/**
 * Minimal sidebar — designed to grow as the data-prep features land.
 * Highlights the active route. Hidden on small screens.
 *
 * Admin-gated items
 * -----------------
 * Some entries (currently "AI connections") only make sense for workspace
 * owners/admins. We read the tenant role from ``useCurrentUser`` — the
 * same call the layout already makes — and hide the link for plain
 * members. The backend RLS gate is the actual boundary; this just keeps
 * the UI tidy.
 */

import { Cog, Database, LayoutDashboard, Shield, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { BrandLogo } from "@/components/brand-logo";
import { useCurrentUser } from "@/hooks/use-current-user";
import type { DictionaryKey } from "@/lib/i18n/dictionaries";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  labelKey: DictionaryKey;
  icon: typeof LayoutDashboard;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { href: "/datasets", labelKey: "nav.datasets", icon: Database },
  { href: "/settings/ai", labelKey: "nav.ai_connections", icon: Sparkles, adminOnly: true },
  { href: "/settings/security", labelKey: "nav.security", icon: Shield },
];

export function Sidebar() {
  const t = useT();
  const pathname = usePathname();
  const { data } = useCurrentUser();
  const isAdmin = data?.tenant.role === "owner" || data?.tenant.role === "admin";
  return (
    <aside className="bg-background hidden w-56 shrink-0 flex-col border-r md:flex">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <BrandLogo className="h-6 w-auto" />
        <span className="text-base font-semibold tracking-tight">{t("brand.name")}</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {NAV_ITEMS.map(({ href, labelKey, icon: Icon, adminOnly }) => {
          if (adminOnly && !isAdmin) return null;
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
              )}
            >
              <Icon className="size-4" />
              {t(labelKey)}
            </Link>
          );
        })}
      </nav>
      <div className="text-muted-foreground p-3 text-xs">
        <Cog className="mr-1 inline size-3" /> v0
      </div>
    </aside>
  );
}
