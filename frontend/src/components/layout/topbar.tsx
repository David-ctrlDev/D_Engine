"use client";

/**
 * Top bar for the authenticated app layout. Workspace name, user email,
 * locale + theme toggles, logout.
 */

import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { LocaleToggle } from "@/components/locale-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { CURRENT_USER_QUERY_KEY } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { useT } from "@/lib/i18n/provider";
import type { TenantPublic, UserPublic } from "@/types/auth";

export function Topbar({ user, tenant }: { user: UserPublic; tenant: TenantPublic }) {
  const t = useT();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  async function handleLogout() {
    setBusy(true);
    try {
      await authApi.logout();
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
      toast.success(t("nav.logout_success"));
      router.replace("/login");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : t("nav.logout_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <header className="bg-background flex h-14 shrink-0 items-center justify-between border-b px-4">
      <div className="flex items-center gap-3">
        <span className="text-muted-foreground text-sm">{t("nav.workspace")}</span>
        <span className="text-sm font-medium">{tenant.name}</span>
      </div>
      <div className="flex items-center gap-1">
        <span className="text-muted-foreground hidden px-2 text-sm md:inline">{user.email}</span>
        <LocaleToggle />
        <ThemeToggle />
        <Button variant="outline" size="sm" onClick={handleLogout} disabled={busy}>
          <LogOut className="size-4" />
          <span className="ml-2 hidden md:inline">{t("nav.logout")}</span>
        </Button>
      </div>
    </header>
  );
}
