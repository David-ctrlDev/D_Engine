"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { useLocale } from "@/lib/i18n/provider";
import type { SessionInfo } from "@/types/auth";

const SESSIONS_QUERY_KEY = ["auth", "sessions"] as const;

export function SessionsTable() {
  const { locale, t } = useLocale();
  const queryClient = useQueryClient();
  const sessionsQuery = useQuery({
    queryKey: SESSIONS_QUERY_KEY,
    queryFn: () => authApi.sessionsList(),
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => authApi.sessionRevoke(id),
    onSuccess: () => {
      toast.success(t("settings.sessions.revoked"));
      queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("settings.sessions.revoke_failed"));
    },
  });

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleString(locale === "es" ? "es-ES" : "en-US");

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.sessions.title")}</CardTitle>
        <CardDescription>{t("settings.sessions.description")}</CardDescription>
      </CardHeader>
      <CardContent>
        {sessionsQuery.isLoading && (
          <p className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" />
            {t("common.loading")}
          </p>
        )}
        {sessionsQuery.error && (
          <p className="text-destructive text-sm">{t("settings.sessions.failed_load")}</p>
        )}
        {sessionsQuery.data && (
          <ul className="divide-y">
            {sessionsQuery.data.sessions.length === 0 && (
              <li className="text-muted-foreground py-4 text-sm">{t("settings.sessions.empty")}</li>
            )}
            {sessionsQuery.data.sessions.map((s: SessionInfo) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">
                      {s.user_agent ?? t("settings.sessions.unknown_device")}
                    </span>
                    {s.is_current && (
                      <Badge variant="secondary">{t("settings.sessions.this_session")}</Badge>
                    )}
                  </div>
                  <p className="text-muted-foreground text-xs">
                    {t("settings.sessions.from")} {s.ip ?? t("settings.sessions.unknown_ip")} ·{" "}
                    {t("settings.sessions.started")} {formatDate(s.created_at)} ·{" "}
                    {t("settings.sessions.expires")} {formatDate(s.expires_at)}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={s.is_current || revokeMutation.isPending}
                  onClick={() => revokeMutation.mutate(s.id)}
                >
                  {s.is_current ? t("settings.sessions.current") : t("settings.sessions.revoke")}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
