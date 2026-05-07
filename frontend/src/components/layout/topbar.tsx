"use client";

/**
 * Top bar for the authenticated app layout. Shows the active workspace
 * name, theme toggle, and a logout control.
 */

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { CURRENT_USER_QUERY_KEY } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import type { TenantPublic, UserPublic } from "@/types/auth";

import { useQueryClient } from "@tanstack/react-query";

export function Topbar({ user, tenant }: { user: UserPublic; tenant: TenantPublic }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  async function handleLogout() {
    setBusy(true);
    try {
      await authApi.logout();
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
      toast.success("Logged out.");
      router.replace("/login");
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Logout failed.";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <header className="bg-background flex h-14 shrink-0 items-center justify-between border-b px-4">
      <div className="flex items-center gap-3">
        <span className="text-muted-foreground text-sm">Workspace</span>
        <span className="text-sm font-medium">{tenant.name}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground hidden text-sm md:inline">{user.email}</span>
        <ThemeToggle />
        <Button variant="outline" size="sm" onClick={handleLogout} disabled={busy}>
          <LogOut className="size-4" />
          <span className="ml-2 hidden md:inline">Logout</span>
        </Button>
      </div>
    </header>
  );
}
