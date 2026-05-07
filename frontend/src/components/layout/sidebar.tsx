"use client";

/**
 * Minimal sidebar — designed to grow as the data-prep features land.
 * Highlights the active route. Hidden on small screens.
 */

import { Cog, Database, LayoutDashboard, Shield } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { BrandLogo } from "@/components/brand-logo";
import type { DictionaryKey } from "@/lib/i18n/dictionaries";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

const NAV_ITEMS: { href: string; labelKey: DictionaryKey; icon: typeof LayoutDashboard }[] = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { href: "/datasets", labelKey: "nav.datasets", icon: Database },
  { href: "/settings/security", labelKey: "nav.security", icon: Shield },
];

export function Sidebar() {
  const t = useT();
  const pathname = usePathname();
  return (
    <aside className="bg-background hidden w-56 shrink-0 flex-col border-r md:flex">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <BrandLogo className="h-6 w-auto" />
        <span className="text-base font-semibold tracking-tight">{t("brand.name")}</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {NAV_ITEMS.map(({ href, labelKey, icon: Icon }) => {
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
