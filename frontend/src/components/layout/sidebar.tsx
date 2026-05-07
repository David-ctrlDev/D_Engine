"use client";

/**
 * Minimal sidebar — designed to grow as the data-prep features land.
 * Highlights the active route and is collapsible to icons on small screens.
 */

import { Cog, LayoutDashboard, Shield } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/settings/security", label: "Security", icon: Shield },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="bg-background hidden w-56 shrink-0 border-r md:block">
      <div className="flex h-14 items-center border-b px-4 text-base font-semibold tracking-tight">
        dataprep
      </div>
      <nav className="flex flex-col gap-1 p-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
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
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="text-muted-foreground mt-auto p-3 text-xs">
        <Cog className="mr-1 inline size-3" /> v0
      </div>
    </aside>
  );
}
